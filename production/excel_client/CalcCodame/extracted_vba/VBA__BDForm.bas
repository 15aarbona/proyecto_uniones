- - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - 




Private Sub UserForm_Initialize()

For Each hoja In ThisWorkbook.Worksheets

If InStr(1, hoja.Name, "O_CAL") = 1 Then

    ListBox1.AddItem (hoja.Name)

End If



Next

End Sub

Private Sub ListBox1_Click()

Dim NombreHoja As String

NombreHoja = ListBox1.value

ThisWorkbook.Worksheets(NombreHoja).Activate

End Sub
-------------------------------------------------------------------------------
VBA MACRO Hoja53.cls 