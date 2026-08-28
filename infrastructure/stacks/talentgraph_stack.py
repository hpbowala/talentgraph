"""TalentGraph MVP stack.

Resources:
- S3 data bucket        cvs/ + vault/ + profiles/ prefixes; the runtime downloads vault/ at
                        cold start and rewrites both when a CV is uploaded or deleted
- DynamoDB table        conversation persistence (app/conversation_store.py)
- Cognito user pool     gates the public API; sign-up disabled, accounts created by hand
- AgentCore Runtime     arm64 container built from backend/, serves the LangGraph app
- Lambda proxy          browser-facing API: signs InvokeAgentRuntime for /chat and /cvs* and
                        reads conversations from DynamoDB directly (list/get/delete)
- CloudFront + S3       serves the built frontend; routes /chat, /conversations* and /cvs* to
                        the Lambda Function URL so the SPA can use same-origin requests

The OpenAI key is NOT a stack resource: create it once as a SecureString parameter
(name from OPENAI_KEY_PARAM in backend/.env) before the first deploy — `make openai-key`.

Nor is the user account: `make cognito-user` creates it after the pool exists, so the
password stays out of CloudFormation. The SPA needs the pool ids at build time, which is
why a clean-slate install deploys twice — see DEPLOYMENT.md.
"""

import os
from pathlib import Path

from aws_cdk import (
    Annotations,
    CfnOutput,
    Duration,
    RemovalPolicy,
    Stack,
)
from aws_cdk import (
    aws_bedrockagentcore as agentcore,
)
from aws_cdk import (
    aws_cloudfront as cloudfront,
)
from aws_cdk import (
    aws_cloudfront_origins as origins,
)
from aws_cdk import (
    aws_cognito as cognito,
)
from aws_cdk import (
    aws_dynamodb as dynamodb,
)
from aws_cdk import (
    aws_ecr_assets as ecr_assets,
)
from aws_cdk import (
    aws_iam as iam,
)
from aws_cdk import (
    aws_lambda as lambda_,
)
from aws_cdk import (
    aws_s3 as s3,
)
from aws_cdk import (
    aws_s3_deployment as s3deploy,
)
from constructs import Construct

REPO_ROOT = Path(__file__).resolve().parents[2]


class TalentGraphStack(Stack):
    def __init__(self, scope: Construct, construct_id: str, **kwargs) -> None:
        super().__init__(scope, construct_id, **kwargs)

        # Names come from backend/.env (loaded by app.py) so backend and infra agree.
        # Bucket names are globally unique, hence the account-id fallback suffix.
        openai_key_param = os.getenv("OPENAI_KEY_PARAM", "/talentgraph/openai-api-key")
        openai_model: str | None = os.getenv("OPENAI_MODEL")
        data_bucket_name = os.getenv("VAULT_BUCKET") or f"talentgraph-data-{self.account}"
        frontend_bucket_name = (
            os.getenv("FRONTEND_BUCKET") or f"talentgraph-frontend-{self.account}"
        )
        table_name = os.getenv("CONVERSATIONS_TABLE", "talentgraph-conversations")

        # Stateful resources (CV corpus, chat history, user accounts) are RETAINed
        # by default, so neither `cdk destroy` nor a property change that forces
        # replacement can take the data with it. Set RETAIN_DATA=false in
        # backend/.env for a throwaway environment you intend to tear down whole.
        retain_data = os.getenv("RETAIN_DATA", "true").strip().lower() not in (
            "false",
            "0",
            "no",
        )
        data_removal = RemovalPolicy.RETAIN if retain_data else RemovalPolicy.DESTROY

        # data
        data_bucket = s3.Bucket(
            self,
            "DataBucket",
            bucket_name=data_bucket_name,
            block_public_access=s3.BlockPublicAccess.BLOCK_ALL,
            encryption=s3.BucketEncryption.S3_MANAGED,
            enforce_ssl=True,
            removal_policy=data_removal,
            # Only ever emptied when the bucket is also being destroyed.
            auto_delete_objects=not retain_data,
        )

        conversations_table = dynamodb.Table(
            self,
            "ConversationsTable",
            table_name=table_name,
            partition_key=dynamodb.Attribute(
                name="conversation_id", type=dynamodb.AttributeType.STRING
            ),
            billing_mode=dynamodb.BillingMode.PAY_PER_REQUEST,
            removal_policy=data_removal,
        )

        # auth
        # Sign-up is disabled: the operator account is created out of band with
        # `make cognito-user`, so no password is ever written to a template.
        user_pool = cognito.UserPool(
            self,
            "UserPool",
            user_pool_name="talentgraph-users",
            self_sign_up_enabled=False,
            sign_in_aliases=cognito.SignInAliases(username=True, email=True),
            password_policy=cognito.PasswordPolicy(
                min_length=12,
                require_lowercase=True,
                require_uppercase=True,
                require_digits=True,
                require_symbols=False,
            ),
            # Recovery is an admin re-running admin-set-user-password, not an
            # email round trip — the pool sends no mail.
            account_recovery=cognito.AccountRecovery.NONE,
            # Retained with the data: dropping the pool would delete every account.
            removal_policy=data_removal,
        )

        # Public SPA client: no secret, because a browser cannot keep one, and
        # SRP only, so the password is proven to Cognito without being sent.
        user_pool_client = user_pool.add_client(
            "SpaClient",
            user_pool_client_name="talentgraph-spa",
            generate_secret=False,
            auth_flows=cognito.AuthFlow(user_srp=True),
            access_token_validity=Duration.hours(1),
            id_token_validity=Duration.hours(1),
            refresh_token_validity=Duration.days(30),
            # One generic error for "no such user" and "wrong password", so a
            # public login form cannot be used to enumerate usernames.
            prevent_user_existence_errors=True,
        )

        # runtime
        image = ecr_assets.DockerImageAsset(
            self,
            "AgentImage",
            directory=str(REPO_ROOT / "backend"),
            platform=ecr_assets.Platform.LINUX_ARM64,
        )

        runtime_role = iam.Role(
            self,
            "RuntimeRole",
            assumed_by=iam.ServicePrincipal("bedrock-agentcore.amazonaws.com"),
            description="Execution role for the TalentGraph AgentCore runtime",
        )
        image.repository.grant_pull(runtime_role)
        # Read for the vault at cold start; write because uploading a CV through the
        # app rewrites cvs/, vault/ and profiles/ (backend/app/cv_store.py).
        data_bucket.grant_read_write(runtime_role)
        data_bucket.grant_delete(runtime_role)
        conversations_table.grant_read_write_data(runtime_role)
        # conversation_store calls table.load() (DescribeTable) on first use
        conversations_table.grant(runtime_role, "dynamodb:DescribeTable")
        runtime_role.add_to_policy(
            iam.PolicyStatement(
                actions=["ecr:GetAuthorizationToken"],
                resources=["*"],
            )
        )
        runtime_role.add_to_policy(
            iam.PolicyStatement(
                actions=[
                    "logs:CreateLogGroup",
                    "logs:CreateLogStream",
                    "logs:PutLogEvents",
                    "logs:DescribeLogGroups",
                    "logs:DescribeLogStreams",
                ],
                resources=[
                    f"arn:aws:logs:{self.region}:{self.account}:log-group:*",
                ],
            )
        )
        runtime_role.add_to_policy(
            iam.PolicyStatement(
                actions=[
                    "xray:PutTraceSegments",
                    "xray:PutTelemetryRecords",
                    "cloudwatch:PutMetricData",
                ],
                resources=["*"],
            )
        )
        runtime_role.add_to_policy(
            iam.PolicyStatement(
                actions=["bedrock-agentcore:GetWorkloadAccessToken"],
                resources=[
                    (
                        f"arn:aws:bedrock-agentcore:{self.region}:{self.account}:"
                        "workload-identity-directory/default"
                    ),
                    (
                        f"arn:aws:bedrock-agentcore:{self.region}:{self.account}:"
                        "workload-identity-directory/default/workload-identity/*"
                    ),
                ],
            )
        )
        runtime_role.add_to_policy(
            iam.PolicyStatement(
                actions=["ssm:GetParameter"],
                resources=[f"arn:aws:ssm:{self.region}:{self.account}:parameter{openai_key_param}"],
            )
        )

        runtime_env = {
            "VAULT_SOURCE": "s3",
            "VAULT_BUCKET": data_bucket.bucket_name,
            "OPENAI_KEY_PARAM": openai_key_param,
            "CONVERSATION_STORE": "dynamodb",
            "CONVERSATIONS_TABLE": conversations_table.table_name,
        }
        if openai_model:
            runtime_env["OPENAI_MODEL"] = openai_model

        runtime = agentcore.CfnRuntime(
            self,
            "Runtime",
            agent_runtime_name="talentgraph",
            description="TalentGraph LangGraph orchestrator",
            agent_runtime_artifact=agentcore.CfnRuntime.AgentRuntimeArtifactProperty(
                container_configuration=agentcore.CfnRuntime.ContainerConfigurationProperty(
                    container_uri=image.image_uri,
                ),
            ),
            network_configuration=agentcore.CfnRuntime.NetworkConfigurationProperty(
                network_mode="PUBLIC",
            ),
            protocol_configuration="HTTP",
            role_arn=runtime_role.role_arn,
            environment_variables=runtime_env,
        )
        runtime.node.add_dependency(runtime_role)

        # proxy
        # A fixed name lets the function grant itself invoke rights without a
        # circular dependency — it re-invokes itself to run reindexes off-request.
        proxy_name = "talentgraph-api-proxy"
        proxy = lambda_.Function(
            self,
            "ApiProxy",
            function_name=proxy_name,
            runtime=lambda_.Runtime.PYTHON_3_13,
            handler="handler.handler",
            code=lambda_.Code.from_asset(str(Path(__file__).resolve().parents[1] / "proxy")),
            # Browser requests are capped by CloudFront's 60s origin timeout; this
            # headroom is for the asynchronous reindex invocation.
            timeout=Duration.minutes(15),
            memory_size=256,
            environment={
                "AGENT_RUNTIME_ARN": runtime.attr_agent_runtime_arn,
                "CONVERSATIONS_TABLE": conversations_table.table_name,
                "DATA_BUCKET": data_bucket.bucket_name,
                "COGNITO_USER_POOL_ID": user_pool.user_pool_id,
            },
            description="Signs AgentCore invocations for the SPA, serves conversation CRUD "
            "and the CV listing, and drives reindexing asynchronously",
        )
        proxy.add_to_role_policy(
            iam.PolicyStatement(
                actions=["bedrock-agentcore:InvokeAgentRuntime"],
                resources=[
                    runtime.attr_agent_runtime_arn,
                    f"{runtime.attr_agent_runtime_arn}/*",
                ],
            )
        )
        proxy.add_to_role_policy(
            iam.PolicyStatement(
                actions=["lambda:InvokeFunction"],
                resources=[f"arn:aws:lambda:{self.region}:{self.account}:function:{proxy_name}"],
            )
        )
        conversations_table.grant_read_write_data(proxy)
        # The CV listing is served straight from the bucket so the SPA can poll it
        # cheaply while a rebuild is running.
        data_bucket.grant_read(proxy)

        function_url = proxy.add_function_url(
            auth_type=lambda_.FunctionUrlAuthType.NONE,
            cors=lambda_.FunctionUrlCorsOptions(
                allowed_origins=["*"],
                allowed_methods=[lambda_.HttpMethod.ALL],
                allowed_headers=["content-type", "authorization"],
            ),
        )

        # frontend
        # Not covered by RETAIN_DATA: this holds the compiled SPA, which every
        # deploy rewrites from source. There is nothing here to lose.
        site_bucket = s3.Bucket(
            self,
            "FrontendBucket",
            bucket_name=frontend_bucket_name,
            block_public_access=s3.BlockPublicAccess.BLOCK_ALL,
            encryption=s3.BucketEncryption.S3_MANAGED,
            enforce_ssl=True,
            removal_policy=RemovalPolicy.DESTROY,
            auto_delete_objects=True,
        )

        api_behavior = cloudfront.BehaviorOptions(
            origin=origins.FunctionUrlOrigin(
                function_url,
                # Uploading a CV runs extraction + a full vault rebuild behind one request.
                read_timeout=Duration.seconds(60),
            ),
            allowed_methods=cloudfront.AllowedMethods.ALLOW_ALL,
            cache_policy=cloudfront.CachePolicy.CACHING_DISABLED,
            origin_request_policy=cloudfront.OriginRequestPolicy.ALL_VIEWER_EXCEPT_HOST_HEADER,
            viewer_protocol_policy=cloudfront.ViewerProtocolPolicy.REDIRECT_TO_HTTPS,
        )

        distribution = cloudfront.Distribution(
            self,
            "Distribution",
            comment="TalentGraph frontend + API",
            default_root_object="index.html",
            default_behavior=cloudfront.BehaviorOptions(
                origin=origins.S3BucketOrigin.with_origin_access_control(site_bucket),
                viewer_protocol_policy=cloudfront.ViewerProtocolPolicy.REDIRECT_TO_HTTPS,
            ),
            additional_behaviors={
                "/chat": api_behavior,
                "/conversations*": api_behavior,
                "/cvs*": api_behavior,
            },
            error_responses=[
                # S3 + OAC answers 403 for unknown keys; hand the SPA its index instead
                cloudfront.ErrorResponse(
                    http_status=403,
                    response_http_status=200,
                    response_page_path="/index.html",
                ),
            ],
        )

        dist_dir = REPO_ROOT / "frontend" / "dist"
        if dist_dir.exists():
            s3deploy.BucketDeployment(
                self,
                "FrontendDeployment",
                sources=[s3deploy.Source.asset(str(dist_dir))],
                destination_bucket=site_bucket,
                distribution=distribution,
                distribution_paths=["/*"],
            )
        else:
            Annotations.of(self).add_warning(
                "frontend/dist not found — run `npm run build` in frontend/ and redeploy "
                "to publish the SPA."
            )

        # outputs
        CfnOutput(self, "DataBucketName", value=data_bucket.bucket_name)
        CfnOutput(self, "ConversationsTableName", value=conversations_table.table_name)
        CfnOutput(self, "AgentRuntimeArn", value=runtime.attr_agent_runtime_arn)
        CfnOutput(self, "ApiFunctionUrl", value=function_url.url)
        CfnOutput(self, "SiteUrl", value=f"https://{distribution.distribution_domain_name}")
        # Read back by `make frontend-build` and baked into the SPA bundle.
        CfnOutput(self, "UserPoolId", value=user_pool.user_pool_id)
        CfnOutput(self, "UserPoolClientId", value=user_pool_client.user_pool_client_id)
