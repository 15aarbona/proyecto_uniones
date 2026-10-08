- - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - 
Private Sub Worksheet_SelectionChange(ByVal Target As Range)

End Sub

Private Sub Worksheet_Change(ByVal Target As Range)
    Dim celdaSelector As Range
    Dim partes() As String
    Dim valorSeleccion As String
    
    On Error GoTo Salida
    Application.EnableEvents = False

    ' Celda con nombre "SelectorPropiedades"
    Set celdaSelector = Me.Range("SelectorPropiedades_SHEAREP")

    ' Si el cambio no afecta al selector, salir
    If Intersect(Target, celdaSelector) Is Nothing Then GoTo Salida

    ' Capturar valor seleccionado
    valorSeleccion = Trim(celdaSelector.value)

    ' Si el valor es "No Aplica" (sin distinguir mayúsculas/minúsculas), salir
    If StrComp(valorSeleccion, "No Aplica", vbTextCompare) = 0 Then
        GoTo Salida
    End If

    ' Dividir por "/"
    partes = Split(valorSeleccion, "/")

    ' Asignar valores limpios
    On Error Resume Next
    Me.Range("ListaNormativa_SHEAREP").value = Trim(partes(0))
    Me.Range("ListaAceroEstructural_SHEAREP").value = Trim(partes(1))
    Me.Range("ListaEstandarTornillos_SHEAREP").value = Trim(partes(2))
    Me.Range("ListaElectrodoSoldadura_SHEAREP").value = Trim(partes(3))
    On Error GoTo 0

Salida:
    Application.EnableEvents = True
End Sub
-------------------------------------------------------------------------------
VBA MACRO Hoja52.cls 