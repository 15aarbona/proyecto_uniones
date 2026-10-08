- - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - 
Public NormativaSeleccionada As String
Public nombreInstancia As String
Public NombreHojaActivaSabana As String

Public Sub Codigo_Propio()

Dim X As Variant, RangoBorrado0 As Range, RangoBorrado1 As Range, RangoBorrado2 As Range, RangoBorrado3 As Range

Call InstanciaObjetoProcesamiento
Call ObtieneNombreInstanciaCodigoCalculo

Dim NombreHojaArchivoConfig As String
NombreHojaArchivoConfig = "MOMENT"

Argumentos = Chr(34) & RutaSabana & Chr(34) & " " _
             & Chr(34) & RutaArchivoConfig & Chr(34) & " " _
             & Chr(34) & RutaBDPerfiles & Chr(34) & " " _
             & nombreInstancia & " " _
             & "AP15" & " " _
             & NombreHojaActivaSabana & " " _
             & NombreHojaArchivoConfig
             
X = Shell(RutaAplicacion + " " + Argumentos, vbMinimizedNoFocus)

End Sub


Public Function ObtieneNombreInstanciaCodigoCalculo() As String

    NombreHojaActivaSabana = ActiveSheet.Name

    Dim hoja As Worksheet
    Dim fila As Integer

    Set hoja = Worksheets("ObjetosTablaBD")

    fila = 2
    While hoja.Cells(fila, 1).value <> NombreHoja And hoja.Cells(fila, 6).value <> NombreHojaActivaSabana

        fila = fila + 1
    Wend

    If NormativaSeleccionada = "AMERICANA" Then
        NombreObjeto = hoja.Cells(fila, 7).value
    ElseIf NormativaSeleccionada = "EUROPEA" Then
        NombreObjeto = hoja.Cells(fila, 8).value
    Else
        MsgBox "Error en la selección de la normativa.", vbCritical
        Exit Function
    End If
    ObtieneNombreInstanciaCodigoCalculo = NombreObjeto
    
    
End Function

Sub SeleccionarNormativa()
    UserFormNormativa.Show
    MsgBox "Normativa seleccionada: " & NormativaSeleccionada, vbInformation
    
    'Obtenemos la clase que queremos
    nombreInstancia = ObtieneNombreInstanciaCodigoCalculo()
    Call Codigo_Propio
    
End Sub

-------------------------------------------------------------------------------
VBA MACRO IU_SCS.bas 