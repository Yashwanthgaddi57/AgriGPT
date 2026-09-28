"use client";

/**
 * Type-ahead combobox for State / District fields. Shows suggestions from a
 * local India geo dataset as the user types; any typed value is still
 * accepted (fields are free text, so unlisted villages/spellings work).
 * Keyboard: ↑/↓ navigate, Enter select, Esc close.
 */
import * as React from "react";
import { MapPin } from "lucide-react";

import { Input } from "@/components/ui/input";

interface Props {
  value: string;
  onChange: (value: string) => void;
  /** Return suggestion strings for the current query. */
  suggestions: (query: string) => string[];
  placeholder?: string;
  id?: string;
  ariaLabel?: string;
}

export function GeoAutocomplete({ value, onChange, suggestions, placeholder, id, ariaLabel }: Props) {
  const [open, setOpen] = React.useState(false);
  const [items, setItems] = React.useState<string[]>([]);
  const [highlight, setHighlight] = React.useState(0);
  const rootRef = React.useRef<HTMLDivElement>(null);
  const inputRef = React.useRef<HTMLInputElement>(null);

  // Close on outside click / tab-away.
  React.useEffect(() => {
    if (!open) return;
    const onDown = (e: PointerEvent) => {
      if (!rootRef.current?.contains(e.target as Node)) setOpen(false);
    };
    document.addEventListener("pointerdown", onDown);
    return () => document.removeEventListener("pointerdown", onDown);
  }, [open]);

  const refresh = (query: string) => {
    const next = suggestions(query);
    setItems(next);
    setHighlight(0);
    setOpen(next.length > 0);
  };

  const pick = (item: string) => {
    onChange(item);
    setOpen(false);
    inputRef.current?.blur();
  };

  const onKeyDown = (e: React.KeyboardEvent<HTMLInputElement>) => {
    if (!open || items.length === 0) return;
    if (e.key === "ArrowDown") {
      e.preventDefault();
      setHighlight((h) => (h + 1) % items.length);
    } else if (e.key === "ArrowUp") {
      e.preventDefault();
      setHighlight((h) => (h - 1 + items.length) % items.length);
    } else if (e.key === "Enter") {
      if (open && items[highlight] && items[highlight] !== value) {
        e.preventDefault();
        pick(items[highlight]);
      }
      // Enter on an already-typed exact value falls through (form submit etc.)
    } else if (e.key === "Escape") {
      setOpen(false);
    }
  };

  return (
    <div ref={rootRef} className="relative">
      <Input
        id={id}
        ref={inputRef}
        role="combobox"
        aria-expanded={open}
        aria-autocomplete="list"
        aria-label={ariaLabel}
        autoComplete="off"
        placeholder={placeholder}
        value={value}
        onChange={(e) => {
          onChange(e.target.value);
          refresh(e.target.value);
        }}
        onFocus={() => refresh(value)}
        onKeyDown={onKeyDown}
      />
      {open && items.length > 0 && (
        <ul
          role="listbox"
          className="absolute z-50 mt-1 max-h-56 w-full overflow-auto rounded-md border bg-popover p-1 shadow-md"
        >
          {items.map((item, i) => (
            <li key={item}>
              <button
                type="button"
                role="option"
                aria-selected={i === highlight}
                className={`flex w-full items-center gap-2 rounded-sm px-2 py-1.5 text-left text-sm ${
                  i === highlight ? "bg-accent text-accent-foreground" : ""
                }`}
                onMouseEnter={() => setHighlight(i)}
                onMouseDown={(e) => {
                  e.preventDefault(); // keep input focus
                  pick(item);
                }}
              >
                <MapPin className="h-3.5 w-3.5 shrink-0 text-leaf-600" />
                {item}
              </button>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}
