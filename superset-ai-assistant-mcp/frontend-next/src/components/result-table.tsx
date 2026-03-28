import { cn } from "@/lib/utils";

interface ResultTableColumn {
  key: string;
  label: string;
  className?: string;
}

interface ResultTableProps {
  columns: ResultTableColumn[];
  rows: Array<Record<string, unknown>>;
  emptyText?: string;
  className?: string;
}

function renderCellValue(value: unknown) {
  if (value === null || value === undefined || value === "") {
    return "—";
  }
  if (typeof value === "object") {
    return JSON.stringify(value);
  }
  return String(value);
}

export function ResultTable({
  columns,
  rows,
  emptyText = "Нет данных для отображения.",
  className,
}: ResultTableProps) {
  if (!rows.length) {
    return (
      <div className={cn("rounded-lg border bg-card px-4 py-6 text-sm text-muted-foreground", className)}>
        {emptyText}
      </div>
    );
  }

  return (
    <div className={cn("overflow-hidden rounded-lg border bg-card", className)}>
      <div className="overflow-x-auto">
        <table className="min-w-full text-sm">
          <thead className="bg-muted/50 text-left">
            <tr>
              {columns.map((column) => (
                <th
                  key={column.key}
                  className={cn(
                    "whitespace-nowrap border-b px-3 py-2 font-medium text-foreground",
                    column.className,
                  )}
                >
                  {column.label}
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {rows.map((row, index) => (
              <tr key={index} className="align-top">
                {columns.map((column) => (
                  <td
                    key={column.key}
                    className={cn(
                      "border-b px-3 py-2 text-muted-foreground",
                      column.className,
                    )}
                  >
                    {renderCellValue(row[column.key])}
                  </td>
                ))}
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}
