- - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - 
Option Explicit

Private NombreHoja As String
Private NombreTabla As String

Public Sub Inicializar(NombreHoja0 As String, NombreTabla0 As String)

    NombreHoja = NombreHoja0
    NombreTabla = NombreTabla0

    If NombreHoja = "" Or NombreTabla = "" Then
        MsgBox "No se ha podido identificar la hoja o la tabla de cálculo.", vbExclamation
        Exit Sub
    End If

    Call CargarConexiones

End Sub

Private Sub UserForm_Initialize()

    lstConexiones.Font.Name = "Calibri"
    lstConexiones.Font.Size = 14

    cmdAceptar.Font.Name = "Calibri"
    cmdAceptar.Font.Size = 14

    cmdTodas.Font.Name = "Calibri"
    cmdTodas.Font.Size = 14

    cmdNinguna.Font.Name = "Calibri"
    cmdNinguna.Font.Size = 14

End Sub

Private Sub CargarConexiones()

    Dim hoja As Worksheet
    Dim Tabla As ListObject
    Dim fila As ListRow
    Dim indiceFila As Long
    Dim valorCalcular As String
    Dim valorUnicode As String

    Set hoja = ThisWorkbook.Worksheets(NombreHoja)
    Set Tabla = hoja.ListObjects(NombreTabla)

    lstConexiones.Clear
    lstConexiones.ColumnCount = 3
    lstConexiones.ColumnWidths = "35;120;80"
    lstConexiones.MultiSelect = fmMultiSelectMulti

    indiceFila = 1

    For Each fila In Tabla.ListRows

        valorCalcular = UCase(Trim(CStr(fila.Range.Cells(1, Tabla.ListColumns("CALCULAR").Index).value)))
        valorUnicode = CStr(fila.Range.Cells(1, Tabla.ListColumns("Unicode").Index).value)

        If Trim(valorUnicode) <> "" Then
            lstConexiones.AddItem indiceFila
            lstConexiones.List(lstConexiones.ListCount - 1, 1) = valorUnicode
            lstConexiones.List(lstConexiones.ListCount - 1, 2) = "Fila " & indiceFila

            If valorCalcular = "SI" Then
                lstConexiones.Selected(lstConexiones.ListCount - 1) = True
            End If
        End If

        indiceFila = indiceFila + 1

    Next fila

End Sub

Private Sub cmdAceptar_Click()

    Dim hoja As Worksheet
    Dim Tabla As ListObject
    Dim i As Long
    Dim indiceFila As Long

    Set hoja = ThisWorkbook.Worksheets(NombreHoja)
    Set Tabla = hoja.ListObjects(NombreTabla)

    For i = 0 To lstConexiones.ListCount - 1

        indiceFila = CLng(lstConexiones.List(i, 0))

        If lstConexiones.Selected(i) Then
            Tabla.ListRows(indiceFila).Range.Cells(1, Tabla.ListColumns("CALCULAR").Index).value = "SI"
        Else
            Tabla.ListRows(indiceFila).Range.Cells(1, Tabla.ListColumns("CALCULAR").Index).value = "NO"
        End If

    Next i

    Unload Me

End Sub

Private Sub cmdTodas_Click()

    Dim i As Long

    For i = 0 To lstConexiones.ListCount - 1
        lstConexiones.Selected(i) = True
    Next i

End Sub

Private Sub cmdNinguna_Click()

    Dim i As Long

    For i = 0 To lstConexiones.ListCount - 1
        lstConexiones.Selected(i) = False
    Next i

End Sub

Private Sub lstConexiones_Click()

End Sub
-------------------------------------------------------------------------------
VBA MACRO Hoja46.cls 