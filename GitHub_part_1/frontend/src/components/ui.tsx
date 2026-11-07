import { useState, type ReactNode } from "react";
import {
  AlertCircle,
  ArrowLeft,
  ChevronLeft,
  ChevronRight,
  CircleCheck,
  Inbox,
  LoaderCircle,
  Search,
} from "lucide-react";
import { Link } from "react-router-dom";
import { errorMessage, labels } from "../lib/format";

export function Header({
  title,
  subtitle,
  eyebrow,
  action,
  back,
}: {
  title: string;
  subtitle: string;
  eyebrow?: string;
  action?: ReactNode;
  back?: { to: string; label: string };
}) {
  return (
    <header className="page-header">
      <div>
        {back && (
          <Link className="back" to={back.to}>
            <ArrowLeft size={16} />
            {back.label}
          </Link>
        )}
        {eyebrow && <div className="eyebrow">{eyebrow}</div>}
        <h1>{title}</h1>
        <p>{subtitle}</p>
      </div>
      {action && <div className="page-action">{action}</div>}
    </header>
  );
}

export function Badge({ value, label }: { value: string; label?: string }) {
  return (
    <span className={`badge badge-${value.toLowerCase()}`}>
      <i />
      {label ?? labels[value] ?? value}
    </span>
  );
}

export function Demo() {
  return <span className="demo-tag">DEMO</span>;
}

export function Notice({
  children,
  success = false,
}: {
  children: ReactNode;
  success?: boolean;
}) {
  const Icon = success ? CircleCheck : AlertCircle;
  return (
    <div
      className={`notice ${success ? "success" : ""}`}
      role={success ? "status" : "alert"}
    >
      <Icon size={18} />
      <div>{children}</div>
    </div>
  );
}

export function QueryState({
  pending,
  error,
}: {
  pending: boolean;
  error: unknown;
}) {
  if (pending)
    return (
      <div className="loading" role="status">
        <LoaderCircle size={19} /> Завантаження…
      </div>
    );
  return error ? <Notice>{errorMessage(error)}</Notice> : null;
}

export function Empty({
  text = "За цими параметрами нічого не знайдено.",
}: {
  text?: string;
}) {
  return (
    <div className="empty">
      <div className="empty-icon">
        <Inbox size={22} />
      </div>
      <strong>{text}</strong>
    </div>
  );
}

export function Panel({
  title,
  subtitle,
  action,
  children,
}: {
  title?: string;
  subtitle?: string;
  action?: ReactNode;
  children: ReactNode;
}) {
  return (
    <section className="panel">
      {title && (
        <header className="panel-head">
          <div>
            <h2>{title}</h2>
            {subtitle && <p>{subtitle}</p>}
          </div>
          {action}
        </header>
      )}
      {children}
    </section>
  );
}

export function Table({
  headings,
  children,
}: {
  headings: string[];
  children: ReactNode;
}) {
  return (
    <div className="table-wrap">
      <table>
        <thead>
          <tr>
            {headings.map((heading) => (
              <th key={heading} scope="col">
                {heading}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>{children}</tbody>
      </table>
    </div>
  );
}

export function Pagination({
  offset,
  limit,
  total,
  change,
}: {
  offset: number;
  limit: number;
  total: number;
  change: (value: number) => void;
}) {
  if (!total && offset === 0) return null;
  return (
    <footer className="pagination">
      <span>
        {total
          ? `${Math.min(offset + 1, total)}–${Math.min(offset + limit, total)} з ${total}`
          : "0 записів"}
      </span>
      <div>
        <button
          className="icon-button"
          aria-label="Попередня сторінка"
          disabled={offset === 0}
          onClick={() => change(Math.max(0, offset - limit))}
        >
          <ChevronLeft size={17} />
        </button>
        <button
          className="icon-button"
          aria-label="Наступна сторінка"
          disabled={offset + limit >= total}
          onClick={() => change(offset + limit)}
        >
          <ChevronRight size={17} />
        </button>
      </div>
    </footer>
  );
}

export function useFilters(initial: Record<string, string> = {}) {
  const [values, setValues] = useState(initial);
  const [offset, setOffset] = useState(0);
  return {
    values,
    offset,
    setOffset,
    set: (key: string, value: string) => {
      setValues((previous) => ({ ...previous, [key]: value }));
      setOffset(0);
    },
  };
}

export function SearchBox({
  value,
  onChange,
  placeholder = "Пошук…",
}: {
  value?: string;
  onChange: (value: string) => void;
  placeholder?: string;
}) {
  return (
    <label className="search">
      <Search size={17} />
      <input
        aria-label="Пошук"
        type="search"
        value={value ?? ""}
        onChange={(event) => onChange(event.target.value)}
        placeholder={placeholder}
      />
    </label>
  );
}

export function SelectFilter({
  label,
  value,
  onChange,
  options,
  empty,
}: {
  label: string;
  value?: string;
  onChange: (value: string) => void;
  options: { value: string | number; label: string }[];
  empty?: string;
}) {
  return (
    <select
      aria-label={label}
      value={value ?? ""}
      onChange={(event) => onChange(event.target.value)}
    >
      {empty !== undefined && <option value="">{empty}</option>}
      {options.map((option) => (
        <option key={option.value} value={option.value}>
          {option.label}
        </option>
      ))}
    </select>
  );
}

export function DateFilter({
  label,
  value,
  onChange,
}: {
  label: string;
  value?: string;
  onChange: (value: string) => void;
}) {
  return (
    <label className="date-filter">
      {label}
      <input
        type="date"
        value={value ?? ""}
        onChange={(event) => onChange(event.target.value)}
      />
    </label>
  );
}

export function Field({
  label,
  children,
  hint,
  error,
}: {
  label: string;
  children: ReactNode;
  hint?: string;
  error?: string;
}) {
  return (
    <label className="field">
      <span>{label}</span>
      {children}
      {hint && <small>{hint}</small>}
      {error && <small className="field-error">{error}</small>}
    </label>
  );
}

export function useAction() {
  const [pending, setPending] = useState(false);
  const [error, setError] = useState("");
  const [success, setSuccess] = useState("");
  const run = async (action: () => Promise<unknown>, message = "") => {
    setPending(true);
    setError("");
    setSuccess("");
    try {
      await action();
      setSuccess(message);
    } catch (cause) {
      setError(errorMessage(cause));
    } finally {
      setPending(false);
    }
  };
  return { pending, error, success, run };
}
