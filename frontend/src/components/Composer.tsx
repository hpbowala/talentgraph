import { useState } from "react";

interface Props {
  disabled: boolean;
  onSubmit: (text: string) => void;
}

export function Composer({ disabled, onSubmit }: Props) {
  const [value, setValue] = useState("");

  return (
    <div className="composer">
      <form
        onSubmit={(e) => {
          e.preventDefault();
          if (!value.trim()) return;
          onSubmit(value);
          setValue("");
        }}
      >
        <input
          value={value}
          onChange={(e) => setValue(e.target.value)}
          placeholder="Ask about people, skills, projects or teams…"
          aria-label="Your question"
          autoFocus
        />
        <button type="submit" disabled={disabled || !value.trim()}>
          Ask
        </button>
      </form>
    </div>
  );
}
