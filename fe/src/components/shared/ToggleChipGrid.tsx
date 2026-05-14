"use client";

type Option<T extends string> = { value: T; label: string };
type Columns = 2 | 3 | 4;

type SingleProps<T extends string, E extends "" | null> = {
  options: ReadonlyArray<Option<T>>;
  multi?: false;
  value: T | E;
  onChange: (value: T | E) => void;
  emptyValue: E;
  columns: Columns;
};

type MultiProps<T extends string> = {
  options: ReadonlyArray<Option<T>>;
  multi: true;
  value: T[];
  onChange: (value: T[]) => void;
  columns: Columns;
};

const COLUMN_CLASS: Record<Columns, string> = {
  2: "grid-cols-2",
  3: "grid-cols-3",
  4: "grid-cols-4",
};

const CHIP_CLASS =
  "rounded-xl border py-2.5 text-[13px] font-semibold transition-colors";
const SELECTED_CLASS = "bg-primary text-primary-foreground border-primary";
const UNSELECTED_CLASS = "border-border bg-muted/50 text-muted-foreground";

export function ToggleChipGrid<T extends string, E extends "" | null = null>(
  props: SingleProps<T, E> | MultiProps<T>,
) {
  return (
    <div className={`grid ${COLUMN_CLASS[props.columns]} gap-2`}>
      {props.options.map((opt) => {
        const selected = props.multi
          ? props.value.includes(opt.value)
          : props.value === opt.value;

        const handleClick = () => {
          if (props.multi) {
            const next = props.value.includes(opt.value)
              ? props.value.filter((v) => v !== opt.value)
              : [...props.value, opt.value];
            props.onChange(next);
          } else {
            props.onChange(
              props.value === opt.value ? props.emptyValue : opt.value,
            );
          }
        };

        return (
          <button
            key={opt.value}
            type="button"
            onClick={handleClick}
            className={`${CHIP_CLASS} ${selected ? SELECTED_CLASS : UNSELECTED_CLASS}`}
          >
            {opt.label}
          </button>
        );
      })}
    </div>
  );
}
