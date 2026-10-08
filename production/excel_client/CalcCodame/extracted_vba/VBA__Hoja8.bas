- - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - 

'Private Sub Worksheet_Activate()
'
'Set CAM_TABLA0 = ClaseNombreBD0.CAM_MOMENT
'
'End Sub

'Private Sub Worksheet_Change(ByVal Target As Range)
'
'Set CAM_TABLA0 = ClaseNombreBD0.CAM_MOMENT
'
'End Sub

'Public Sub AsignaObjetoCam_Tabla()
'
'Set CAM_TABLA0 = ClaseNombreBD0.CAM_MOMENT
'
'End Sub
Private Sub Worksheet_SelectionChange(ByVal Target As Range)

End Sub

Private Sub Worksheet_Change(ByVal Target As Range)
    Dim celdaSelector As Range
    Dim partes() As String
    Dim valorSeleccion As String
    
    On Error GoTo Salida
    Application.EnableEvents = False

    ' Celda con nombre "SelectorPropiedades"
    Set celdaSelector = Me.Range("SelectorPropiedades")

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
    Me.Range("ListaNormativa").value = Trim(partes(0))
    Me.Range("ListaAceroEstructural").value = Trim(partes(1))
    Me.Range("ListaEstandarTornillos").value = Trim(partes(2))
    Me.Range("ListaElectrodoSoldadura").value = Trim(partes(3))
    On Error GoTo 0

Salida:
    Application.EnableEvents = True
End Sub


-------------------------------------------------------------------------------
VBA MACRO Hoja54.cls 