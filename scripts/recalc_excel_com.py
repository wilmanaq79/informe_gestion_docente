"""Recalcula y guarda un .xlsx abriendolo con Excel instalado localmente (COM),
como alternativa a LibreOffice (no disponible en esta maquina Windows).
Uso: python recalc_excel_com.py archivo.xlsx
"""
import sys
import os
import win32com.client as win32

def recalc(path):
    path = os.path.abspath(path)
    excel = win32.gencache.EnsureDispatch("Excel.Application")
    excel.Visible = False
    excel.DisplayAlerts = False
    try:
        wb = excel.Workbooks.Open(path)
        excel.CalculateFullRebuild()
        wb.Save()
        wb.Close(SaveChanges=True)
    finally:
        excel.Quit()

if __name__ == "__main__":
    recalc(sys.argv[1])
    print("Recalculado:", sys.argv[1])
