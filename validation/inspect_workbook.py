"""
Introspeccion READ-ONLY de un libro .xlsm via COM (Excel). NO ejecuta macros
(AutomationSecurity=ForceDisable) y NO guarda cambios.

Uso:
    python inspect_workbook.py "ruta\\al\\libro.xlsm"
"""
import sys
import json
import win32com.client as win32

MSO_AUTOMATION_SECURITY_FORCE_DISABLE = 3
XL_UPDATE_LINKS_NEVER = 0


def col_list_to_2d(val):
    if val is None:
        return []
    if isinstance(val, tuple):
        if val and isinstance(val[0], tuple):
            return [list(r) for r in val]
        return [list(val)]
    return [[val]]


def inspect(path):
    xl = win32.DispatchEx("Excel.Application")
    xl.Visible = False
    xl.DisplayAlerts = False
    xl.EnableEvents = False
    xl.ScreenUpdating = False
    try:
        xl.AutomationSecurity = MSO_AUTOMATION_SECURITY_FORCE_DISABLE
    except Exception:
        pass
    wb = None
    try:
        wb = xl.Workbooks.Open(
            Filename=path,
            ReadOnly=True,
            UpdateLinks=XL_UPDATE_LINKS_NEVER,
            IgnoreReadOnlyRecommended=True,
            AddToMru=False,
        )
        out = {"path": path, "sheets": [], "named_ranges": []}

        for ws in wb.Worksheets:
            sh = {"name": ws.Name, "tables": []}
            try:
                for t in ws.ListObjects:
                    try:
                        hdr = col_list_to_2d(t.HeaderRowRange.Value)[0]
                    except Exception:
                        hdr = []
                    try:
                        addr = t.Range.Address
                    except Exception:
                        addr = ""
                    sh["tables"].append({
                        "name": t.Name,
                        "address": addr,
                        "headers": hdr,
                    })
            except Exception as e:
                sh["tables_error"] = str(e)
            out["sheets"].append(sh)

        try:
            for nm in wb.Names:
                out["named_ranges"].append({"name": nm.Name, "refers_to": nm.RefersTo})
        except Exception as e:
            out["named_ranges_error"] = str(e)

        return out
    finally:
        if wb is not None:
            wb.Close(SaveChanges=False)
        xl.Quit()


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print(__doc__)
        sys.exit(2)
    data = inspect(sys.argv[1])
    payload = json.dumps(data, ensure_ascii=False, indent=2, default=str)
    sys.stdout.buffer.write(payload.encode("utf-8"))
