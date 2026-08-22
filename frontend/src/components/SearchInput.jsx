import { Search, X } from "lucide-react"
import { Input } from "@/components/ui/input"

/**
 * Reusable search field with a leading icon (and optional clear button).
 * Replaces the duplicated search-input markup found across multiple pages.
 */
export default function SearchInput({
  value,
  onChange,
  placeholder = "ค้นหา...",
  wrapperClassName = "relative flex-1",
  inputClassName = "",
  onClear,
  id,
}) {
  return (
    <div className={wrapperClassName}>
      <Search className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" />
      <Input
        id={id}
        type="text"
        placeholder={placeholder}
        value={value}
        onChange={onChange}
        className={`pl-9 ${onClear ? "pr-9" : ""} ${inputClassName}`}
      />
      {onClear && value ? (
        <button
          type="button"
          onClick={onClear}
          className="absolute right-2 top-1/2 flex h-6 w-6 -translate-y-1/2 items-center justify-center rounded-md text-muted-foreground transition-colors hover:bg-accent hover:text-foreground"
          aria-label="ล้างคำค้นหา"
        >
          <X className="h-4 w-4" />
        </button>
      ) : null}
    </div>
  )
}
