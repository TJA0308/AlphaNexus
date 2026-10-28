import type { ReactNode } from "react";

type Row = Record<string, string | number>;

export function DataTable({ rows, emptyMessage, actions }: {
  rows: Row[]; emptyMessage: string; actions?: (index: number) => ReactNode;
}) {
  if (rows.length === 0) {
    return <div className="empty-table">{emptyMessage}</div>;
  }

  const headers = Object.keys(rows[0]);

  return (
    <div className="table-wrap">
      <table>
        <thead>
          <tr>
            {headers.map((header) => (
              <th key={header}>{header.replaceAll("_", " ")}</th>
            ))}
            {actions ? <th>Actions</th> : null}
          </tr>
        </thead>
        <tbody>
          {rows.map((row, index) => (
            <tr key={index}>
              {headers.map((header) => (
                <td key={header}>{row[header]}</td>
              ))}
              {actions ? <td>{actions(index)}</td> : null}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
