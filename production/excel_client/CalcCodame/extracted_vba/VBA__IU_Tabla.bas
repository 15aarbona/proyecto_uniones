- - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - 
Public CAM_TABLA0 As CAMPOS_TABLA
Public CAM_TABLA0_CALC As CAMPOS_TABLA

Public Function ObtieneNombreObjetoTablaBD() As String
    Dim NombreBoton As String
    Dim contador As Long
    If TypeName(Application.Caller) = "String" Then
        NombreBoton = Application.Caller
    End If
    NombreHoja = ActiveSheet.Name

    Dim hoja As Worksheet
    Dim fila As Integer

    Set hoja = Worksheets("ObjetosTablaBD")

    fila = 2
    While hoja.Cells(fila, 1).value <> NombreHoja And hoja.Cells(fila, 6).value <> NombreHoja

        fila = fila + 1
        contador = contador + 1
        If contador > 10000 Then
            ObtieneNombreObjetoTablaBD = "" ' o puedes poner "No encontrado", o lanzar un MsgBox
            Exit Function
        End If

    Wend
    NombreObjetoTablaBD = hoja.Cells(fila, 2).value
    ObtieneNombreObjetoTablaBD = NombreObjetoTablaBD
    
    
End Function

Public Function ObtieneCampoTabla() As CAMPOS_TABLA
    Dim NombreHoja As String
    Dim CAM_TABLA0 As CAMPOS_TABLA  ' Declaramos la variable correctamente

    NombreHoja = ActiveSheet.Name

    Select Case NombreHoja
        Case "IU_MOMENT"
            Set CAM_TABLA0 = ClaseNombreBD0.CAM_MOMENT
        Case "IM_MOMENT"
            Set CAM_TABLA0 = ClaseNombreBD0.CAM_MOMENT_CALC
        Case "IM_MOMENT"
            Set CAM_TABLA0 = ClaseNombreBD0.CAM_MOMENT_CALC_EXCEL
        Case "IU_FLUSHEP"
            Set CAM_TABLA0 = ClaseNombreBD0.CAM_FLUSHEP
        Case "IM_FLUSHEP"
            Set CAM_TABLA0 = ClaseNombreBD0.CAM_FLUSHEP_CALC
        Case "IU_SPLICECP"
            Set CAM_TABLA0 = ClaseNombreBD0.CAM_SPLICECP
        Case "IU_SPLICEEP"
            Set CAM_TABLA0 = ClaseNombreBD0.CAM_SPLICEEP
        Case "IU_BRACING"
            Set CAM_TABLA0 = ClaseNombreBD0.CAM_BRACING
        Case "IM_BRACING"
            Set CAM_TABLA0 = ClaseNombreBD0.CAM_BRACING_CALC
        Case "IU_BRACINGEP"
            Set CAM_TABLA0 = ClaseNombreBD0.CAM_BRACINGEP
        Case "IU_SHEAREP"
            Set CAM_TABLA0 = ClaseNombreBD0.CAM_SHEAREP
        Case "IM_SHEAREP"
            Set CAM_TABLA0 = ClaseNombreBD0.CAM_SHEAREP_CALC
        Case "IM_SHEAREP_EXCEL"
            Set CAM_TABLA0 = ClaseNombreBD0.CAM_SHEAREP_CALC_EXCEL
        Case "IU_SHEAREXP"
            Set CAM_TABLA0 = ClaseNombreBD0.CAM_SHEAREXP
        Case "IU_BRACINGHOR"
            Set CAM_TABLA0 = ClaseNombreBD0.CAM_BRACINGHOR
        Case "MW_CF"
            Set CAM_TABLA0 = ClaseNombreBD0.CAM_MW_CF
        Case "MW_CW"
            Set CAM_TABLA0 = ClaseNombreBD0.CAM_MW_CW
        Case "MW_B"
            Set CAM_TABLA0 = ClaseNombreBD0.CAM_MW_B
        Case "MW_B02"
            Set CAM_TABLA0 = ClaseNombreBD0.CAM_MW_B02
        Case "MW_B03"
            Set CAM_TABLA0 = ClaseNombreBD0.CAM_MW_B03
        Case "MW_N"
            Set CAM_TABLA0 = ClaseNombreBD0.CAM_MW_N
        
        'Case Else
            'MsgBox "Nombre de hoja no válido", vbExclamation
            'Exit Function
    End Select

    Set ObtieneCampoTabla = CAM_TABLA0  ' Devolvemos el objeto correctamente
End Function

Public Function ObtieneCampoCALC() As CAMPOS_TABLA
    Dim NombreHoja As String
    Dim CAM_TABLA0_CALC As CAMPOS_TABLA  ' Declaramos la variable correctamente

    NombreHoja = ActiveSheet.Name

    Select Case NombreHoja
        Case "IU_MOMENT", "IM_MOMENT_EXCEL"
            Set CAM_TABLA0_CALC = ClaseNombreBD0.CAM_MOMENT_CALC
        Case "IM_MOMENT"
            Set CAM_TABLA0_CALC = ClaseNombreBD0.CAM_MOMENT
            
        Case "IU_FLUSHEP", "IM_FLUSHEP_EXCEL"
            Set CAM_TABLA0_CALC = ClaseNombreBD0.CAM_FLUSHEP_CALC
        Case "IM_FLUSHEP"
            Set CAM_TABLA0_CALC = ClaseNombreBD0.CAM_FLUSHEP
            
        Case "IU_SPLICECP", "IM_SPLICECP_EXCEL"
            Set CAM_TABLA0_CALC = ClaseNombreBD0.CAM_SPLICECP_CALC
            
        Case "IU_SPLICEEP", "IM_SPLICEEP_EXCEL"
            Set CAM_TABLA0_CALC = ClaseNombreBD0.CAM_SPLICEEP_CALC
            
        Case "IU_BRACING", "IM_BRACING_EXCEL"
            Set CAM_TABLA0_CALC = ClaseNombreBD0.CAM_BRACING_CALC
        Case "IM_BRACING"
            Set CAM_TABLA0_CALC = ClaseNombreBD0.CAM_BRACING
            
        Case "IU_BRACINGEP", "IM_BRACINGEP_EXCEL"
            Set CAM_TABLA0_CALC = ClaseNombreBD0.CAM_BRACINGEP_CALC
            
        Case "IU_SHEAREP", "IM_SHEAREP_EXCEL"
            Set CAM_TABLA0_CALC = ClaseNombreBD0.CAM_SHEAREP_CALC
        Case "IM_SHEAREP"
            Set CAM_TABLA0_CALC = ClaseNombreBD0.CAM_SHEAREP
            
        Case "IU_SHEAREXP", "IM_SHEAREXP_EXCEL"
            Set CAM_TABLA0_CALC = ClaseNombreBD0.CAM_SHEAREXP_CALC
            
        Case "IU_BRACINGHOR", "IM_BRACINGHOR_EXCEL"
            Set CAM_TABLA0_CALC = ClaseNombreBD0.CAM_BRACINGHOR_CALC
    End Select

    Set ObtieneCampoCALC = CAM_TABLA0_CALC  ' Devolvemos el objeto correctamente
End Function

Public Function ObtieneCampoCALCExcel() As CAMPOS_TABLA
    Dim NombreHoja As String
    Dim CAM_TABLA0_CALC As CAMPOS_TABLA

    NombreHoja = ActiveSheet.Name

    Select Case NombreHoja
        Case "IU_MOMENT", "IM_MOMENT_EXCEL"
            Set CAM_TABLA0_CALC = ClaseNombreBD0.CAM_MOMENT_CALC_EXCEL

        Case "IU_FLUSHEP", "IM_FLUSHEP_EXCEL"
            Set CAM_TABLA0_CALC = ClaseNombreBD0.CAM_FLUSHEP_CALC_EXCEL

        Case "IU_SPLICECP", "IM_SPLICECP_EXCEL"
            Set CAM_TABLA0_CALC = ClaseNombreBD0.CAM_SPLICECP_CALC_EXCEL

        Case "IU_SPLICEEP", "IM_SPLICEEP_EXCEL"
            Set CAM_TABLA0_CALC = ClaseNombreBD0.CAM_SPLICEEP_CALC_EXCEL

        Case "IU_BRACING", "IM_BRACING_EXCEL"
            Set CAM_TABLA0_CALC = ClaseNombreBD0.CAM_BRACING_CALC_EXCEL

        Case "IU_BRACINGEP", "IM_BRACINGEP_EXCEL"
            Set CAM_TABLA0_CALC = ClaseNombreBD0.CAM_BRACINGEP_CALC_EXCEL

        Case "IU_SHEAREP", "IM_SHEAREP_EXCEL"
            Set CAM_TABLA0_CALC = ClaseNombreBD0.CAM_SHEAREP_CALC_EXCEL

        Case "IU_SHEAREXP", "IM_SHEAREXP_EXCEL"
            Set CAM_TABLA0_CALC = ClaseNombreBD0.CAM_SHEAREXP_CALC_EXCEL

        Case Else
            MsgBox "Nombre de hoja no válido: " & NombreHoja, vbExclamation
            Exit Function
    End Select

    Set ObtieneCampoCALCExcel = CAM_TABLA0_CALC
End Function

Public Function ObtieneCampoCALCMathcad() As CAMPOS_TABLA
    Dim NombreHoja As String
    Dim CAM_TABLA0_CALC As CAMPOS_TABLA

    NombreHoja = ActiveSheet.Name

    Select Case NombreHoja
        Case "IU_MOMENT", "IM_MOMENT_MATHCAD"
            Set CAM_TABLA0_CALC = ClaseNombreBD0.CAM_MOMENT_CALC_MATHCAD

        Case "IU_FLUSHEP", "IM_FLUSHEP_MATHCAD"
            Set CAM_TABLA0_CALC = ClaseNombreBD0.CAM_FLUSHEP_CALC_MATHCAD

        Case "IU_SPLICECP", "IM_SPLICECP_MATHCAD"
            Set CAM_TABLA0_CALC = ClaseNombreBD0.CAM_SPLICECP_CALC_MATHCAD

        Case "IU_SPLICEEP", "IM_SPLICEEP_MATHCAD"
            Set CAM_TABLA0_CALC = ClaseNombreBD0.CAM_SPLICEEP_CALC_MATHCAD

        Case "IU_BRACING", "IM_BRACING_MATHCAD"
            Set CAM_TABLA0_CALC = ClaseNombreBD0.CAM_BRACING_CALC_MATHCAD

        Case "IU_BRACINGEP", "IM_BRACINGEP_MATHCAD"
            Set CAM_TABLA0_CALC = ClaseNombreBD0.CAM_BRACINGEP_CALC_MATHCAD

        Case "IU_SHEAREP", "IM_SHEAREP_MATHCAD"
            Set CAM_TABLA0_CALC = ClaseNombreBD0.CAM_SHEAREP_CALC_MATHCAD

        Case "IU_SHEAREXP", "IM_SHEAREXP_MATHCAD"
            Set CAM_TABLA0_CALC = ClaseNombreBD0.CAM_SHEAREXP_CALC_MATHCAD

        Case Else
            MsgBox "Nombre de hoja no válido: " & NombreHoja, vbExclamation
            Exit Function
    End Select

    Set ObtieneCampoCALCMathcad = CAM_TABLA0_CALC
End Function

Public Function ObtieneCampoCALCSCS() As CAMPOS_TABLA
    Dim NombreHoja As String
    Dim CAM_TABLA0_CALC As CAMPOS_TABLA  ' Declaramos la variable correctamente

    NombreHoja = ActiveSheet.Name

    Select Case NombreHoja
        Case "IU_MOMENT"
            Set CAM_TABLA0_CALC = ClaseNombreBD0.CAM_MOMENT_CALC_SCS
        Case "IM_MOMENT_SCS"
            Set CAM_TABLA0_CALC = ClaseNombreBD0.CAM_MOMENT
        Case "IU_FLUSHEP"
            Set CAM_TABLA0_CALC = ClaseNombreBD0.CAM_FLUSHEP_CALC_SCS
        Case "IM_FLUSHEP_SCS"
            Set CAM_TABLA0_CALC = ClaseNombreBD0.CAM_FLUSHEP
        Case "IU_SPLICECP"
            Set CAM_TABLA0_CALC = ClaseNombreBD0.CAM_SPLICECP_CALC_SCS
        Case "IM_SPLICECP"
            Set CAM_TABLA0_CALC = ClaseNombreBD0.CAM_SPLICECP_CALC
        Case "IU_SPLICEEP"
            Set CAM_TABLA0_CALC = ClaseNombreBD0.CAM_SPLICEEP_CALC_SCS
        Case "IM_SPLICEEP_EXCEL"
            Set CAM_TABLA0_CALC = ClaseNombreBD0.CAM_SPLICEEP
        Case "IU_BRACING"
            Set CAM_TABLA0_CALC = ClaseNombreBD0.CAM_BRACING_CALC_EXCEL
        Case "IM_BRACING"
            Set CAM_TABLA0_CALC = ClaseNombreBD0.CAM_BRACING
        Case "IU_BRACINGEP"
            Set CAM_TABLA0_CALC = ClaseNombreBD0.CAM_BRACINGEP_CALC_SCS
        Case "IM_BRACINGEP"
            Set CAM_TABLA0_CALC = ClaseNombreBD0.CAM_BRACINGEP
        Case "IU_SHEAREP"
            Set CAM_TABLA0_CALC = ClaseNombreBD0.CAM_SHEAREP_CALC_SCS
        Case "IM_SHEAREP_EXCEL"
            Set CAM_TABLA0_CALC = ClaseNombreBD0.CAM_SHEAREP
        Case "IU_SHEAREXP"
            Set CAM_TABLA0_CALC = ClaseNombreBD0.CAM_SHEAREXP_CALC
        Case "IU_BRACINGHOR"
            Set CAM_TABLA0_CALC = ClaseNombreBD0.CAM_BRACINGHOR_CALC
        Case Else
            MsgBox "Nombre de hoja no válido", vbExclamation
            Exit Function
    End Select

    Set ObtieneCampoCALCSCS = CAM_TABLA0_CALC  ' Devolvemos el objeto correctamente
End Function

Public Function ObtieneCampoCALCTEKLA() As CAMPOS_TABLA
    Dim NombreHoja As String
    Dim CAM_TABLA0_CALC As CAMPOS_TABLA  ' Declaramos la variable correctamente

    NombreHoja = ActiveSheet.Name

    Select Case NombreHoja
        Case "IU_MOMENT"
            Set CAM_TABLA0_CALC = ClaseNombreBD0.CAM_MOMENT_CALC_SCS
        Case "IM_MOMENT_SCS"
            Set CAM_TABLA0_CALC = ClaseNombreBD0.CAM_MOMENT
        Case "IU_FLUSHEP"
            Set CAM_TABLA0_CALC = ClaseNombreBD0.CAM_FLUSHEP_CALC_TEKLA
        Case "IM_FLUSHEP_TEKLA"
            Set CAM_TABLA0_CALC = ClaseNombreBD0.CAM_FLUSHEP
        Case "IU_SPLICECP"
            Set CAM_TABLA0_CALC = ClaseNombreBD0.CAM_SPLICECP_CALC_SCS
        Case "IM_SPLICECP"
            Set CAM_TABLA0_CALC = ClaseNombreBD0.CAM_SPLICECP_CALC
        Case "IU_SPLICEEP"
            Set CAM_TABLA0_CALC = ClaseNombreBD0.CAM_SPLICEEP_CALC_SCS
        Case "IM_SPLICEEP_EXCEL"
            Set CAM_TABLA0_CALC = ClaseNombreBD0.CAM_SPLICEEP
        Case "IU_BRACING"
            Set CAM_TABLA0_CALC = ClaseNombreBD0.CAM_BRACING_CALC_EXCEL
        Case "IM_BRACING"
            Set CAM_TABLA0_CALC = ClaseNombreBD0.CAM_BRACING
        Case "IU_BRACINGEP"
            Set CAM_TABLA0_CALC = ClaseNombreBD0.CAM_BRACINGEP_CALC_SCS
        Case "IM_BRACINGEP"
            Set CAM_TABLA0_CALC = ClaseNombreBD0.CAM_BRACINGEP
        Case "IU_SHEAREP"
            Set CAM_TABLA0_CALC = ClaseNombreBD0.CAM_SHEAREP_CALC_SCS
        Case "IM_SHEAREP_EXCEL"
            Set CAM_TABLA0_CALC = ClaseNombreBD0.CAM_SHEAREP
        Case "IU_SHEAREXP"
            Set CAM_TABLA0_CALC = ClaseNombreBD0.CAM_SHEAREXP_CALC
        Case "IU_BRACINGHOR"
            Set CAM_TABLA0_CALC = ClaseNombreBD0.CAM_BRACINGHOR_CALC
        Case Else
            MsgBox "Nombre de hoja no válido", vbExclamation
            Exit Function
    End Select

    Set ObtieneCampoCALCTEKLA = CAM_TABLA0_CALC  ' Devolvemos el objeto correctamente
End Function

Public Function ObtieneCampoProcesarCALCSCS() As CAMPOS_TABLA
    Dim NombreHoja As String
    Dim CAM_TABLA0_CALC As CAMPOS_TABLA  ' Declaramos la variable correctamente

    NombreHoja = ActiveSheet.Name

    Select Case NombreHoja
        Case "IM_MOMENT_SCS"
            Set CAM_TABLA0_CALC = ClaseNombreBD0.CAM_MOMENT_CALC_SCS
        Case "IM_FLUSHEP_SCS"
            Set CAM_TABLA0_CALC = ClaseNombreBD0.CAM_FLUSHEP_CALC_SCS
        Case "IM_SPLICEEP_SCS"
            Set CAM_TABLA0_CALC = ClaseNombreBD0.CAM_SPLICEEP_CALC_SCS
        Case "IM_SPLICECP_SCS"
            Set CAM_TABLA0_CALC = ClaseNombreBD0.CAM_SPLICECP_CALC_SCS
        Case "IM_SHEAREP_SCS"
            Set CAM_TABLA0_CALC = ClaseNombreBD0.CAM_SHEAREP_CALC_SCS
        Case "IM_BRACINGEP_SCS"
            Set CAM_TABLA0_CALC = ClaseNombreBD0.CAM_BRACINGEP_CALC_SCS
        Case "IM_BRACING_SCS"
            Set CAM_TABLA0_CALC = ClaseNombreBD0.CAM_BRACING_CALC_SCS
        
        
    End Select

    Set ObtieneCampoProcesarCALCSCS = CAM_TABLA0_CALC  ' Devolvemos el objeto correctamente
End Function

Public Function ObtieneCampoProcesarCALCCODAME() As CAMPOS_TABLA
    Dim NombreHoja As String
    Dim CAM_TABLA0_CALC As CAMPOS_TABLA  ' Declaramos la variable correctamente

    NombreHoja = ActiveSheet.Name

    Select Case NombreHoja
        Case "IM_FLUSHEP"
            Set CAM_TABLA0_CALC = ClaseNombreBD0.CAM_FLUSHEP_CALC
        Case "IM_MOMENT"
            Set CAM_TABLA0_CALC = ClaseNombreBD0.CAM_MOMENT_CALC
        Case "IM_BRACING"
            Set CAM_TABLA0_CALC = ClaseNombreBD0.CAM_BRACING_CALC
        Case "IM_BRACINGEP"
            Set CAM_TABLA0_CALC = ClaseNombreBD0.CAM_BRACINGEP_CALC
        Case "IM_SHEAREP"
            Set CAM_TABLA0_CALC = ClaseNombreBD0.CAM_SHEAREP_CALC
        Case "IM_SHEAREXP"
            Set CAM_TABLA0_CALC = ClaseNombreBD0.CAM_SHEAREXP_CALC
        Case "IM_SPLICEEP"
            Set CAM_TABLA0_CALC = ClaseNombreBD0.CAM_SPLICEEP_CALC
        Case "IM_SPLICECP"
            Set CAM_TABLA0_CALC = ClaseNombreBD0.CAM_SPLICECP_CALC
        Case "IM_BRACINGHOR"
            Set CAM_TABLA0_CALC = ClaseNombreBD0.CAM_BRACINGHOR_CALC
        
        Case "IM_MOMENT_EXCEL"
            Set CAM_TABLA0_CALC = ClaseNombreBD0.CAM_MOMENT_CALC_EXCEL
        Case "IM_FLUSHEP_EXCEL"
            Set CAM_TABLA0_CALC = ClaseNombreBD0.CAM_FLUSHEP_CALC_EXCEL
        
        Case Else
            Err.Raise vbObjectError + 1003, "ObtieneCampoProcesarCALCCODAME", "No existe configuración de tabla CODAME para: " & NombreHoja
            
        
    End Select

    Set ObtieneCampoProcesarCALCCODAME = CAM_TABLA0_CALC  ' Devolvemos el objeto correctamente
End Function

Public Function ObtieneCampoProcesarCALCEXCEL() As CAMPOS_TABLA
    Dim NombreHoja As String
    Dim CAM_TABLA0_CALC As CAMPOS_TABLA

    NombreHoja = ActiveSheet.Name

    Select Case NombreHoja
        Case "IU_MOMENT"
            Set CAM_TABLA0_CALC = ClaseNombreBD0.CAM_MOMENT_CALC_EXCEL
        Case "IM_MOMENT_EXCEL"
            Set CAM_TABLA0_CALC = ClaseNombreBD0.CAM_MOMENT_CALC_EXCEL
        Case "IU_FLUSHEP"
            Set CAM_TABLA0_CALC = ClaseNombreBD0.CAM_FLUSHEP_CALC_EXCEL
        Case "IM_FLUSHEP_EXCEL"
            Set CAM_TABLA0_CALC = ClaseNombreBD0.CAM_FLUSHEP_CALC_EXCEL
        Case "IU_SHEAREP"
            Set CAM_TABLA0_CALC = ClaseNombreBD0.CAM_SHEAREP_CALC_EXCEL
        Case "IM_SHEAREP_EXCEL"
            Set CAM_TABLA0_CALC = ClaseNombreBD0.CAM_SHEAREP_CALC_EXCEL
        Case "IU_SPLICEEP"
            Set CAM_TABLA0_CALC = ClaseNombreBD0.CAM_SPLICEEP_CALC_EXCEL
        Case "IM_SPLICEEP_EXCEL"
            Set CAM_TABLA0_CALC = ClaseNombreBD0.CAM_SPLICEEP_CALC_EXCEL
        Case "IU_BRACING"
            Set CAM_TABLA0_CALC = ClaseNombreBD0.CAM_BRACING_CALC_EXCEL
        Case "IM_BRACING_EXCEL"
            Set CAM_TABLA0_CALC = ClaseNombreBD0.CAM_BRACING_CALC_EXCEL
        Case "IU_BRACINGEP"
            Set CAM_TABLA0_CALC = ClaseNombreBD0.CAM_BRACINGEP_CALC_EXCEL
        Case "IM_BRACINGEP_EXCEL"
            Set CAM_TABLA0_CALC = ClaseNombreBD0.CAM_BRACINGEP_CALC_EXCEL
        Case "IU_SHEAREXP"
            Set CAM_TABLA0_CALC = ClaseNombreBD0.CAM_SHEAREXP_CALC_EXCEL
        Case "IM_SHEAREXP_EXCEL"
            Set CAM_TABLA0_CALC = ClaseNombreBD0.CAM_SHEAREXP_CALC_EXCEL
        Case "IU_SPLICECP"
            Set CAM_TABLA0_CALC = ClaseNombreBD0.CAM_SPLICECP_CALC_EXCEL
        Case "IM_SPLICECP_EXCEL"
            Set CAM_TABLA0_CALC = ClaseNombreBD0.CAM_SPLICECP_CALC_EXCEL
            
            
    End Select

    Set ObtieneCampoProcesarCALCEXCEL = CAM_TABLA0_CALC

End Function

Public Function ObtieneCampoBDDesdeCALCExcel() As CAMPOS_TABLA

    Select Case ActiveSheet.Name
        Case "IM_MOMENT_EXCEL"
            Set ObtieneCampoBDDesdeCALCExcel = ClaseNombreBD0.CAM_MOMENT
        Case "IM_FLUSHEP_EXCEL"
            Set ObtieneCampoBDDesdeCALCExcel = ClaseNombreBD0.CAM_FLUSHEP
        Case "IM_SPLICECP_EXCEL"
            Set ObtieneCampoBDDesdeCALCExcel = ClaseNombreBD0.CAM_SPLICECP
        Case "IM_SPLICEEP_EXCEL"
            Set ObtieneCampoBDDesdeCALCExcel = ClaseNombreBD0.CAM_SPLICEEP
        Case "IM_BRACING_EXCEL"
            Set ObtieneCampoBDDesdeCALCExcel = ClaseNombreBD0.CAM_BRACING
        Case "IM_BRACINGEP_EXCEL"
            Set ObtieneCampoBDDesdeCALCExcel = ClaseNombreBD0.CAM_BRACINGEP
        Case "IM_SHEAREP_EXCEL"
            Set ObtieneCampoBDDesdeCALCExcel = ClaseNombreBD0.CAM_SHEAREP
        Case "IM_SHEAREXP_EXCEL"
            Set ObtieneCampoBDDesdeCALCExcel = ClaseNombreBD0.CAM_SHEAREXP
        Case Else
            MsgBox "Hoja no válida para inversa Excel: " & ActiveSheet.Name, vbCritical
    End Select
End Function


Public Function ObtieneNombreCodigoBDyCalculoyPrincipal() As Variant
    Dim NombreBoton As String
    Dim NombreHoja As String
    Dim NombreCodigoBD As String
    Dim NombreCalculo As String
    Dim NombreClasePrincipal As String
    
    If TypeName(Application.Caller) = "String" Then
        NombreBoton = Application.Caller
    End If
    
    NombreHoja = ActiveSheet.Name
    
    Dim hoja As Worksheet
    Dim fila As Integer
    
    Set hoja = Worksheets("ObjetosTablaBD")
    
    fila = 2
    While hoja.Cells(fila, 1).value <> NombreHoja And hoja.Cells(fila, 6).value <> NombreHoja
     
        fila = fila + 1
    Wend
    
    NombreCodigoBD = hoja.Cells(fila, 3).value
    NombreCalculo = hoja.Cells(fila, 4).value
    NombreClasePrincipal = hoja.Cells(fila, 5).value

    ' Devolver como array
    ObtieneNombreCodigoBDyCalculoyPrincipal = Array(NombreClasePrincipal, NombreCodigoBD, NombreCalculo)
End Function

Public Function ObtieneNombreCodigoBDyCalculoExcelYPrincipal() As Variant
    Dim NombreHoja As String
    Dim NombreCodigoBD As String
    Dim NombreCalculo As String
    Dim NombreClasePrincipal As String

    NombreHoja = ActiveSheet.Name

    Dim hoja As Worksheet
    Dim fila As Long

    Set hoja = Worksheets("ObjetosTablaBD")

    fila = 2
    While hoja.Cells(fila, 1).value <> NombreHoja And hoja.Cells(fila, 9).value <> NombreHoja
    fila = fila + 1
    Wend

    NombreCodigoBD = hoja.Cells(fila, 3).value
    NombreCalculo = hoja.Cells(fila, 10).value
    NombreClasePrincipal = hoja.Cells(fila, 5).value

    ObtieneNombreCodigoBDyCalculoExcelYPrincipal = Array(NombreClasePrincipal, NombreCodigoBD, NombreCalculo)
End Function

Public Function ObtieneNombreCodigoBDyCalculoMathcad() As Variant
    Dim NombreHoja As String
    Dim NombreCodigoBD As String
    Dim NombreCalculo As String
    Dim NombreClasePrincipal As String

    NombreHoja = ActiveSheet.Name

    Dim hoja As Worksheet
    Dim fila As Long

    Set hoja = Worksheets("ObjetosTablaBD")

    fila = 2
    While hoja.Cells(fila, 1).value <> NombreHoja And hoja.Cells(fila, 9).value <> NombreHoja
    fila = fila + 1
    Wend

    NombreCodigoBD = hoja.Cells(fila, 3).value
    NombreCalculoMATHCAD = hoja.Cells(fila, 15).value
    NombreClasePrincipal = hoja.Cells(fila, 5).value

    ObtieneNombreCodigoBDyCalculoMathcad = Array(NombreClasePrincipal, NombreCodigoBD, NombreCalculoMATHCAD)
End Function

Public Function ObtieneNombreCodigoBDyCalculoSCS() As Variant
    Dim NombreBoton As String
    Dim NombreHoja As String
    Dim NombreCodigoBD As String
    Dim NombreCalculo As String
    Dim NombreClasePrincipal As String
    
    If TypeName(Application.Caller) = "String" Then
        NombreBoton = Application.Caller
    End If
    
    NombreHoja = ActiveSheet.Name
    
    Dim hoja As Worksheet
    Dim fila As Integer
    
    Set hoja = Worksheets("ObjetosTablaBD")
    
    fila = 2
    While hoja.Cells(fila, 1).value <> NombreHoja And hoja.Cells(fila, 9).value <> NombreHoja
     
        fila = fila + 1
    Wend
    
    NombreCodigoBD = hoja.Cells(fila, 3).value
    NombreCalculoSCS = hoja.Cells(fila, 12).value
    NombreClasePrincipal = hoja.Cells(fila, 5).value

    ' Devolver como array
    ObtieneNombreCodigoBDyCalculoSCS = Array(NombreClasePrincipal, NombreCodigoBD, NombreCalculoSCS)
End Function

Public Function ObtieneNombreCodigoBDyCalculoTEKLA() As Variant
    Dim NombreBoton As String
    Dim NombreHoja As String
    Dim NombreCodigoBD As String
    Dim NombreCalculo As String
    Dim NombreClasePrincipal As String
    
    If TypeName(Application.Caller) = "String" Then
        NombreBoton = Application.Caller
    End If
    
    NombreHoja = ActiveSheet.Name
    
    Dim hoja As Worksheet
    Dim fila As Integer
    
    Set hoja = Worksheets("ObjetosTablaBD")
    
    fila = 2
    While hoja.Cells(fila, 1).value <> NombreHoja And hoja.Cells(fila, 9).value <> NombreHoja
     
        fila = fila + 1
    Wend
    
    NombreCodigoBD = hoja.Cells(fila, 3).value
    NombreCalculoTEKLA = hoja.Cells(fila, 14).value
    NombreClasePrincipal = hoja.Cells(fila, 5).value

    ' Devolver como array
    ObtieneNombreCodigoBDyCalculoTEKLA = Array(NombreClasePrincipal, NombreCodigoBD, NombreCalculoTEKLA)
End Function

Public Sub DetectaBotonAccion()

Dim NombreObjetoTablaBD As String
Dim NombreBoton As String
Dim NombreHoja As String
Dim Eliminar As Boolean
Dim Nombres As Variant
Dim DatosMotorExcel As Variant



'/**************************
'CODIGO PROPIO

'Para la Transformacion
NombreObjetoTablaBD = ObtieneNombreObjetoTablaBD()

'Para cualquier accion
Set CAM_TABLA0 = ObtieneCampoTabla()

NombreBoton = Application.Caller

If NombreBoton = "INSERTAR" Then Call TABLA_INSERTAR("INSERTAR", RutaLibroExcel, CAM_TABLA0, ClaseNombreBD0.CAM_Auxiliar, "MOMENT", NombreObjetoTablaBD)
If NombreBoton = "CARGARPORPROYECTO" Then Call TABLA_CARGARPORPROYECTO("CARGARPORPROYECTO", RutaLibroExcel, CAM_TABLA0, ClaseNombreBD0.CAM_Auxiliar, NombreObjetoTablaBD)
If NombreBoton = "CARGARPORFILTROS" Then Call TABLA_CARGARPORFILTROS("CARGARPORFILTROS", RutaLibroExcel, CAM_TABLA0, ClaseNombreBD0.CAM_Auxiliar, NombreObjetoTablaBD)
If NombreBoton = "ELIMINAR" Then
    
    Call EliminarElementoConConfirmacion(Eliminar)
    If Eliminar Then Call TABLA_ELIMINAR("ELIMINAR", RutaLibroExcel, CAM_TABLA0, ClaseNombreBD0.CAM_Auxiliar, NombreObjetoTablaBD)
End If


If NombreBoton = "INSERTAR_AMS" Then Call TABLA_INSERTAR_AMS("INSERTAR_AMS", RutaLibroExcel, CAM_TABLA0, ClaseNombreBD0.CAM_Auxiliar, NombreObjetoTablaBD)
If NombreBoton = "ELIMINAR_AMS" Then
    
    Call EliminarElementoConConfirmacion(Eliminar)
    If Eliminar Then Call TABLA_ELIMINAR_AMS("ELIMINAR_AMS", RutaLibroExcel, CAM_TABLA0, ClaseNombreBD0.CAM_Auxiliar, NombreObjetoTablaBD)
End If

If NombreBoton = "CARGAR_LISTA_PROYECTOS" Then Call TABLA_CARGAR_PROYECTOS("CARGAR_PROYECTOS", RutaLibroExcel, ClaseNombreBD0.CAM_Auxiliar)
If NombreBoton = "CARGAR_LISTA_FILTROS" Then Call TABLA_CARGAR_FILTROS("CARGAR_FILTROS", RutaLibroExcel, CAM_TABLA0, ClaseNombreBD0.CAM_Auxiliar)

'TRANSFORMACION CON MOTOR DE CALCULO
If NombreBoton = "MOTOR_CALCULO" Then
    Set CAM_TABLA0_CALC = ObtieneCampoCALC()
    Nombres = ObtieneNombreCodigoBDyCalculoyPrincipal()
    Call TABLA_PROPIEDADES("DIRECCION_CODIGOCALC", RutaLibroExcel, CAM_TABLA0, CAM_TABLA0_CALC, ClaseNombreBD0.CAM_Auxiliar, Nombres)
End If

If NombreBoton = "MOTOR_BBDD" Then
    Set CAM_TABLA0_CALC = ObtieneCampoCALC()
    Nombres = ObtieneNombreCodigoBDyCalculoyPrincipal()
    Call TABLA_PROPIEDADES("DIRECCION_BBDD", RutaLibroExcel, CAM_TABLA0, CAM_TABLA0_CALC, ClaseNombreBD0.CAM_Auxiliar, Nombres)
End If

If NombreBoton = "MOTOR_BBDD_EXCEL" Then
    Set CAM_TABLA0 = ObtieneCampoBDDesdeCALCExcel()
    Set CAM_TABLA0_CALC = ObtieneCampoCALCExcel()
    
    Nombres = ObtieneNombreCodigoBDyCalculoExcelYPrincipal()
    
    Call TABLA_PROPIEDADES("DIRECCION_EXCEL_CODIGOCALC", RutaLibroExcel, CAM_TABLA0_CALC, CAM_TABLA0, ClaseNombreBD0.CAM_Auxiliar, Nombres)
End If

'Procesamiento no implementado


'/**************************
'EXCEL DE JORGE
'If NombreBoton = "MOTOR_CALCULO_EXCEL" Then
    'Actualizamos CODIGO_CALC
    'Set CAM_TABLA0_CALC = ObtieneCampoCALCExcel()
    'Nombres = ObtieneNombreCodigoBDyCalculoExcel()
    'Call TABLA_PROPIEDADES("DIRECCION_CODIGOCALC_EXCEL", RutaLibroExcel, CAM_TABLA0, CAM_TABLA0_CALC, ClaseNombreBD0.CAM_Auxiliar, Nombres)
'End If

'If NombreBoton = "MOTOR_BBDD_EXCEL" Then
    'Set CAM_TABLA0_CALC = ObtieneCampoCALCExcel()
    'Nombres = ObtieneNombreCodigoBDyCalculoExcel()
    'Call TABLA_PROPIEDADES("DIRECCION_EXCEL_CODIGOCALC", RutaLibroExcel, CAM_TABLA0, CAM_TABLA0_CALC, ClaseNombreBD0.CAM_Auxiliar, Nombres)
'End If

'El procesamiento de los ratios del Excel de Jorge se hace con una macro directamente


'/**************************
'TRANSFORMACION SCS
If NombreBoton = "MOTOR_TRANSFORMACION_SCS" Then
    Set CAM_TABLA0_CALC = ObtieneCampoCALCSCS()
    Nombres = ObtieneNombreCodigoBDyCalculoSCS()
    Call TABLA_PROPIEDADES("DIRECCION_BBDD_SCS", RutaLibroExcel, CAM_TABLA0, CAM_TABLA0_CALC, ClaseNombreBD0.CAM_Auxiliar, Nombres)
End If
'PROCESAMIENTO CODIGO PROPIO CON SCS
If NombreBoton = "MOTOR_CALCULO_SCS" Then
    Set CAM_TABLA0 = ObtieneCampoProcesarCALCSCS()
    Call TABLA_SCS("PROCESAR_SCS", RutaLibroExcel, CAM_TABLA0, ClaseNombreBD0.CAM_Auxiliar)
End If

'PROCESAMIENTO CODIGO PROPIO CON CODAME
If NombreBoton = "MOTOR_CALCULO_CODAME" Then
    Set CAM_TABLA0 = ObtieneCampoProcesarCALCCODAME()
    Call TABLA_CODAME("CALCULAR_CODAME", RutaLibroExcel, CAM_TABLA0, ClaseNombreBD0.CAM_Auxiliar)
End If

If NombreBoton = "MOTOR_DIMENSIONAMIENTO_CODAME" Then
    Set CAM_TABLA0 = ObtieneCampoProcesarCALCCODAME()
    Call TABLA_CODAME("DIMENSIONAMIENTO_CODAME", RutaLibroExcel, CAM_TABLA0, ClaseNombreBD0.CAM_Auxiliar)
End If

If NombreBoton = "MOTOR_PARAMETROS_AUX_CODAME" Then
    Set CAM_TABLA0 = ObtieneCampoProcesarCALCCODAME()
    Call TABLA_CODAME("PARAMETROS_AUX_CODAME", RutaLibroExcel, CAM_TABLA0, ClaseNombreBD0.CAM_Auxiliar)

End If

'/********************
'TRANSFORMACION TEKLA
If NombreBoton = "MOTOR_TRANSFORMACION_TEKLA" Then
    Set CAM_TABLA0_CALC = ObtieneCampoCALCTEKLA()
    Nombres = ObtieneNombreCodigoBDyCalculoTEKLA()
    Call TABLA_PROPIEDADES("DIRECCION_BBDD_TEKLA", RutaLibroExcel, CAM_TABLA0, CAM_TABLA0_CALC, ClaseNombreBD0.CAM_Auxiliar, Nombres)
End If

'/**********************
'TRANSFORMACION PARA HOJAS DE EXCEL
If NombreBoton = "MOTOR_TRANSFORMACION_EXCEL" Then
    Set CAM_TABLA0_CALC = ObtieneCampoCALCExcel()
    Nombres = ObtieneNombreCodigoBDyCalculoExcelYPrincipal()
    Call TABLA_PROPIEDADES("DIRECCION_CODIGOCALC_EXCEL", RutaLibroExcel, CAM_TABLA0, CAM_TABLA0_CALC, ClaseNombreBD0.CAM_Auxiliar, Nombres)
End If

'PROCESAMIENTO CON HOJAS DE EXCEL
If NombreBoton = "MOTOR_CALCULO_EXCEL" Then
    Set CAM_TABLA0 = ObtieneCampoProcesarCALCEXCEL()
    DatosMotorExcel = ObtieneNombreCodigoProcesaCalculoEXCELENGINE()
    Call TABLA_EXCELENGINE("CALCULAR_EXCEL", RutaLibroExcel, CAM_TABLA0, DatosMotorExcel, ClaseNombreBD0.CAM_Auxiliar)
End If

'/**********************
'TRANSFORMACION PARA MATHCAD
If NombreBoton = "MOTOR_TRANSFORMACION_MATHCAD" Then
    Set CAM_TABLA0_CALC = ObtieneCampoCALCMathcad()
    Nombres = ObtieneNombreCodigoBDyCalculoMathcad()
    Call TABLA_PROPIEDADES("DIRECCION_CODIGOCALC_MATHCAD", RutaLibroExcel, CAM_TABLA0, CAM_TABLA0_CALC, ClaseNombreBD0.CAM_Auxiliar, Nombres)
End If

'CALCULO MATHCAD
If NombreBoton = "MOTOR_MATHCAD" Then
    
End If

End Sub


Public Sub TABLA_INSERTAR(Accion As String, RutaLibroExcel As String, CAM_TABLA0 As CAMPOS_TABLA, CAM_AUXILIAR0 As CAMPOS_Auxiliar, TablaEliminaUnicode As String, NombreObjetoTablaBD As String)
Dim Rango As Range
Dim Permiso As String
Set Rango = Hoja6.Range(ClaseNombreBD0.CAM_Auxiliar.HabilitarObjetos)
Permiso = Rango.value
    ' Verificamos si el usuario tiene permisos de escritura
    If Permiso = "AMBAS" Or Permiso = "ESCRITURA" Then

        Dim X As Variant
        Dim RangoBorrado(0 To 3) As Range
        Dim Argumentos As String
        Dim i As Integer


        ' Crear o asegurar la instancia de conexión a base de datos
        Call InstanciaObjetoBD

        ' Preparar argumentos para la llamada al proceso externo
        Argumentos = Accion & " " & Chr(34) & RutaLibroExcel & Chr(34) & " " & _
                     DatosTablaInterfaz(EsLectura, ThisWorkbook, CAM_TABLA0.NombreHoja, CAM_TABLA0.Tabla, RangoBorrado(0)) & " " & _
                     DatosNombreInterfaz(Not EsLectura, ThisWorkbook, CAM_AUXILIAR0.MensajeAdvertenciaUnicode, RangoBorrado(1)) & " " & _
                     DatosNombreInterfaz(Not EsLectura, ThisWorkbook, CAM_AUXILIAR0.TablaEliminaUnicode, RangoBorrado(2)) & " " & _
                     DatosNombreInterfaz(Not EsLectura, ThisWorkbook, CAM_AUXILIAR0.MensajeError, RangoBorrado(3)) & " " & _
                     CAM_TABLA0.Tabla & " " & _
                     NombreObjetoTablaBD

        ' Borramos el contenido de los rangos intermedios
        For i = 1 To 3
            If Not RangoBorrado(i) Is Nothing Then
                RangoBorrado(i).ClearContents
            End If
        Next i

        ' Escribir en la tabla auxiliar antes de insertar
        Range(CAM_AUXILIAR0.TablaEliminaUnicode).value = TablaEliminaUnicode


        ' Ejecutar el proceso externo
        X = Shell(RutaAplicacion & " " & Argumentos, vbMinimizedNoFocus)

    Else
        MsgBox "You do not have the necessary permissions to perform this action.", vbExclamation
    End If

End Sub


Public Sub TABLA_CARGARPORFILTROS(Accion As String, RutaLibroExcel As String, CAM_TABLA0 As CAMPOS_TABLA, CAM_AUXILIAR0 As CAMPOS_Auxiliar, NombreObjetoTablaBD As String)

Dim X As Variant, RangoBorrado(0 To 11) As Range

Call InstanciaObjetoBD

a = MontarFiltrosInterfaz(EsLectura, CAM_TABLA0, RangoBorrado)
b = DatosNombreInterfaz(Not EsLectura, ThisWorkbook, CAM_AUXILIAR0.MensajeError, RangoBorrado(11))

Argumentos = Accion & " " & Chr(34) & RutaLibroExcel & Chr(34) & " " _
                & "InicioFiltros" & " " _
                & MontarFiltrosInterfaz(EsLectura, CAM_TABLA0, RangoBorrado) _
                & "FinalFiltros" & " " _
                & DatosTablaInterfaz(Not EsLectura, ThisWorkbook, CAM_TABLA0.NombreHoja, CAM_TABLA0.Tabla, RangoBorrado(10)) & " " _
                & DatosNombreInterfaz(Not EsLectura, ThisWorkbook, CAM_AUXILIAR0.MensajeError, RangoBorrado(11)) & " " _
                & CAM_TABLA0.Tabla & " " _
                & NombreObjetoTablaBD
    
For i = 10 To 11

    RangoBorrado(i).ClearContents

Next

IU_Auxiliar.ResetearFiltroProyecto


X = Shell(RutaAplicacion + " " + Argumentos, vbMinimizedNoFocus)

End Sub

Private Function MontarFiltrosInterfaz(EsLectura As Boolean, _
    CAM_TABLA0 As CAMPOS_TABLA, _
    ByRef RangoBorrado_() As Range) As String

    Dim texto As String
    Dim RangoBorrado As Range
    Set RangoBorrado = ActiveCell

texto = ""

    AgregarFiltroInterfaz texto, EsLectura, CAM_TABLA0.ListaNormativa, RangoBorrado
    
    AgregarFiltroInterfaz texto, EsLectura, CAM_TABLA0.ListaAceroEstructural, RangoBorrado
    AgregarFiltroInterfaz texto, EsLectura, CAM_TABLA0.ListaElectrodoSoldadura, RangoBorrado
    AgregarFiltroInterfaz texto, EsLectura, CAM_TABLA0.ListaEstandarTornillos, RangoBorrado
    AgregarFiltroInterfaz texto, EsLectura, CAM_TABLA0.ListaCalculationTool, RangoBorrado
    AgregarFiltroInterfaz texto, EsLectura, CAM_TABLA0.ListaSource, RangoBorrado
    AgregarFiltroInterfaz texto, EsLectura, CAM_TABLA0.ListaDesignation, RangoBorrado
    AgregarFiltroInterfaz texto, EsLectura, CAM_TABLA0.ListaCapacityMoment, RangoBorrado
    AgregarFiltroInterfaz texto, EsLectura, CAM_TABLA0.ListaCapacityShear, RangoBorrado
    AgregarFiltroInterfaz texto, EsLectura, CAM_TABLA0.ListaCapacityAxial, RangoBorrado
    AgregarFiltroInterfaz texto, EsLectura, CAM_TABLA0.ListaCapacityShearSA, RangoBorrado

    MontarFiltrosInterfaz = texto

End Function

Public Sub TABLA_CARGARPORPROYECTO(Accion As String, RutaLibroExcel As String, CAM_TABLA0 As CAMPOS_TABLA, CAM_AUXILIAR0 As CAMPOS_Auxiliar, NombreObjetoTablaBD As String)

Dim X As Variant, RangoBorrado(0 To 5) As Range

Call InstanciaObjetoBD

Argumentos = Accion & " " & Chr(34) & RutaLibroExcel & Chr(34) & " " _
             & DatosNombreInterfaz(EsLectura, ThisWorkbook, CAM_TABLA0.ListaProyectoAMS, RangoBorrado(1)) & " " _
             & DatosTablaInterfaz(Not EsLectura, ThisWorkbook, CAM_TABLA0.NombreHoja, CAM_TABLA0.Tabla, RangoBorrado(2)) & " " _
             & DatosNombreInterfaz(Not EsLectura, ThisWorkbook, CAM_AUXILIAR0.MensajeError, RangoBorrado(3)) & " " _
             & CAM_TABLA0.Tabla & " " _
             & NombreObjetoTablaBD

For i = 2 To 3

    RangoBorrado(i).ClearContents

Next

IU_Auxiliar.ResetearFiltroNormativa
IU_Auxiliar.ResetearFiltroAceroEstructural
IU_Auxiliar.ResetearFiltroElectrodoSoldadura
IU_Auxiliar.ResetearFiltroEstandarTornillos

X = Shell(RutaAplicacion + " " + Argumentos, vbMinimizedNoFocus)

End Sub



Public Sub TABLA_CARGAR_PROYECTOS(Accion As String, RutaLibroExcel As String, CAM_AUXILIAR0 As CAMPOS_Auxiliar)

Dim X As Variant, RangoBorrado(0 To 1) As Range

Call InstanciaObjetoBD

Argumentos = Accion & " " & Chr(34) & RutaLibroExcel & Chr(34) & " " _
             & DatosNombreInterfaz(Not EsLectura, ThisWorkbook, CAM_AUXILIAR0.Lista_NombreProyectos, RangoBorrado(0)) & " " _
             & DatosNombreInterfaz(Not EsLectura, ThisWorkbook, CAM_AUXILIAR0.MensajeError, RangoBorrado(1))

For i = 1 To 1

    RangoBorrado(i).ClearContents

Next

X = Shell(RutaAplicacion + " " + Argumentos, vbMinimizedNoFocus)

End Sub

Public Sub TABLA_CARGAR_FILTROS(Accion As String, RutaLibroExcel As String, CAM_TABLA0 As CAMPOS_TABLA, CAM_AUXILIAR0 As CAMPOS_Auxiliar)

Dim X As Variant, RangoBorrado(0 To 14) As Range

Call InstanciaObjetoBD

Argumentos = Accion & " " & Chr(34) & RutaLibroExcel & Chr(34) & " " _
             & DatosNombreInterfaz(Not EsLectura, ThisWorkbook, CAM_AUXILIAR0.Lista_NombreNormativa, RangoBorrado(0)) & " " _
             & DatosNombreInterfaz(Not EsLectura, ThisWorkbook, CAM_AUXILIAR0.Lista_NombreElectrodoSoldadura, RangoBorrado(1)) & " " _
             & DatosNombreInterfaz(Not EsLectura, ThisWorkbook, CAM_AUXILIAR0.Lista_NombreAceroEstructural, RangoBorrado(2)) & " " _
             & DatosNombreInterfaz(Not EsLectura, ThisWorkbook, CAM_AUXILIAR0.Lista_NombreEstandarTornillos, RangoBorrado(3)) & " " _
             & DatosNombreInterfaz(Not EsLectura, ThisWorkbook, CAM_AUXILIAR0.Lista_NombreCalculationTool, RangoBorrado(4)) & " " _
             & DatosNombreInterfaz(Not EsLectura, ThisWorkbook, CAM_AUXILIAR0.Lista_NombreSource, RangoBorrado(5)) & " " _
             & DatosNombreInterfaz(Not EsLectura, ThisWorkbook, CAM_AUXILIAR0.Lista_NombreDesignation, RangoBorrado(6)) & " " _
             & "FinalFiltros" & " " _
             & DatosNombreInterfaz(Not EsLectura, ThisWorkbook, CAM_AUXILIAR0.MensajeError, RangoBorrado(7)) & " " _
             & DatosNombreInterfaz(EsLectura, ThisWorkbook, CAM_TABLA0.ListaNormativa, RangoBorrado(8)) & " " _
             & DatosNombreInterfaz(EsLectura, ThisWorkbook, CAM_TABLA0.ListaElectrodoSoldadura, RangoBorrado(9)) & " " _
             & DatosNombreInterfaz(EsLectura, ThisWorkbook, CAM_TABLA0.ListaAceroEstructural, RangoBorrado(10)) & " " _
             & DatosNombreInterfaz(EsLectura, ThisWorkbook, CAM_TABLA0.ListaEstandarTornillos, RangoBorrado(11)) & " " _
             & DatosNombreInterfaz(EsLectura, ThisWorkbook, CAM_TABLA0.ListaCalculationTool, RangoBorrado(12)) & " " _
             & DatosNombreInterfaz(EsLectura, ThisWorkbook, CAM_TABLA0.ListaSource, RangoBorrado(13)) & " " _
             & DatosNombreInterfaz(EsLectura, ThisWorkbook, CAM_TABLA0.ListaDesignation, RangoBorrado(14)) & " " _

RangoBorrado(0).ClearContents
RangoBorrado(1).ClearContents
RangoBorrado(2).ClearContents
RangoBorrado(3).ClearContents
RangoBorrado(4).ClearContents
RangoBorrado(5).ClearContents
RangoBorrado(6).ClearContents
RangoBorrado(7).ClearContents

X = Shell(RutaAplicacion + " " + Argumentos, vbMinimizedNoFocus)

End Sub

'Permite quedarnos con la lista acotada de filtros
Public Sub RehacerNombreLista(ByRef Lista As String, ByRef ListaAcotada As String)

Dim Con0 As Integer
Dim Rango As Range, hoja As Worksheet
Dim FilaIni As Integer, ColuIni As Integer, Filai As Integer, Colui As Integer

'Electrodo Soldadura
Set Rango = ThisWorkbook.Names.Item(Lista).RefersToRange
Set hoja = ThisWorkbook.Worksheets(ClaseNombreBD0.CAM_Auxiliar.NombreHoja)

FilaIni = Rango.Row
ColuIni = Rango.column

Con0 = 0
Filai = FilaIni
Colui = ColuIni

While Not IsEmpty(hoja.Cells(Filai, Colui).value)
  
    Filai = Filai + 1
    Con0 = Con0 + 1

Wend

Set Rango = hoja.Range(hoja.Cells(FilaIni, ColuIni), hoja.Cells(Filai - 1, Colui))

ThisWorkbook.Names.Item(ListaAcotada).RefersTo = Rango


End Sub

Public Sub TABLA_ELIMINAR(Accion As String, RutaLibroExcel As String, CAM_TABLA0 As CAMPOS_TABLA, CAM_AUXILIAR0 As CAMPOS_Auxiliar, NombreObjetoTablaBD As String)

    Dim X As Variant, RangoBorrado(0 To 1) As Range
    
    Call InstanciaObjetoBD
    
    Argumentos = Accion & " " & Chr(34) & RutaLibroExcel & Chr(34) & " " _
                 & DatosTablaInterfaz(EsLectura, ThisWorkbook, CAM_TABLA0.NombreHoja, CAM_TABLA0.Tabla, RangoBorrado(0)) & " " _
                 & DatosNombreInterfaz(Not EsLectura, ThisWorkbook, CAM_AUXILIAR0.MensajeError, RangoBorrado(1)) & " " _
                 & CAM_TABLA0.Tabla & " " _
                 & NombreObjetoTablaBD
                 
    For i = 1 To 1
    
        RangoBorrado(i).ClearContents
    
    Next
    
    
    X = Shell(RutaAplicacion + " " + Argumentos, vbMinimizedNoFocus)


    
End Sub

Sub EliminarElementoConConfirmacion(Eliminar As Boolean)
Dim Rango As Range
Dim Permiso As String
Set Rango = Hoja6.Range(ClaseNombreBD0.CAM_Auxiliar.HabilitarObjetos)
Permiso = Rango.value
' Verificamos si el usuario tiene permisos de escritura
If Permiso = "AMBAS" Or Permiso = "ESCRITURA" Then
    Dim respuesta As VbMsgBoxResult
    Dim normativaValores As String
    Dim proyectoValores As String
    Dim i As Long
    Dim mensaje

    
    mensaje = "Are you sure you want to delete these connections?"

    ' Mostrar el cuadro de mensaje con dos opciones: Sí o No
    respuesta = MsgBox(mensaje, vbYesNo + vbQuestion, "Confirmación de eliminación")
    
    ' Verificar la respuesta del usuario
    If respuesta = vbYes Then
        Eliminar = True
        MsgBox "El elemento ha sido eliminado.", vbInformation, "Successful deletion."
        ' Aquí puedes poner el código para eliminar el elemento
    Else
        Eliminar = False
        ' Código para volver atrás
        MsgBox "Operation cancelled.", vbExclamation, "Cancelled"
        ' Aquí puedes poner el código para retroceder o cancelar la operación
    End If

Else
    MsgBox "You do not have the necessary permissions to perform this action.", vbExclamation
End If


End Sub

Public Sub TABLA_PROPIEDADES(Accion As String, RutaLibroExcel As String, CAM_TABLA0 As CAMPOS_TABLA, CAM_TABLA1 As CAMPOS_TABLA, CAM_AUXILIAR0 As CAMPOS_Auxiliar, Nombres As Variant)

Dim Rango As Range
Dim Permiso As String
Set Rango = Hoja6.Range(ClaseNombreBD0.CAM_Auxiliar.HabilitarObjetos)
Permiso = Rango.value
    ' Verificamos si el usuario tiene permisos de escritura
If Permiso = "AMBAS" Or Permiso = "ESCRITURA" Then
    Dim X As Variant, RangoBorrado(0 To 1) As Range
    
    Call InstanciaObjetoBD
        
    Argumentos = Accion & " " & Chr(34) & RutaLibroExcel & Chr(34) & " " _
                 & DatosNombreInterfaz(Not EsLectura, ThisWorkbook, CAM_AUXILIAR0.Lista_Propiedades_CodigoCalc, RangoBorrado(0)) & " " _
                 & DatosNombreInterfaz(Not EsLectura, ThisWorkbook, CAM_AUXILIAR0.MensajeError, RangoBorrado(1)) & " " _
                 & CAM_TABLA0.Tabla & " " _
                 & CAM_TABLA1.Tabla & " " _
                 & CAM_TABLA0.NombreHoja & " " _
                 & CAM_TABLA1.NombreHoja & " " _
                 & Nombres(0) & " " _
                 & Nombres(1) & " " _
                 & Nombres(2)
    
    
    For i = 1 To 1
    
        RangoBorrado(i).ClearContents
    
    Next
    
    'MsgBox "RutaLibroExcel = " & RutaLibroExcel & vbCrLf & _
       '"ThisWorkbook.FullName = " & ThisWorkbook.FullName & vbCrLf & _
       '"ThisWorkbook.Name = " & ThisWorkbook.Name
       
    'MsgBox Argumentos

    
    X = Shell(RutaAplicacion + " " + Argumentos, vbMinimizedNoFocus)
Else
    MsgBox "You do not have the necessary permissions to perform this action.", vbExclamation
End If

End Sub


'
Public Sub TABLA_INSERTAR_AMS(Accion As String, RutaLibroExcel As String, CAM_TABLA0 As CAMPOS_TABLA, CAM_AUXILIAR0 As CAMPOS_Auxiliar, NombreObjetoTablaBD As String)
Dim Rango As Range
Dim Permiso As String
Set Rango = Hoja6.Range(ClaseNombreBD0.CAM_Auxiliar.HabilitarObjetos)
Permiso = Rango.value
    ' Verificamos si el usuario tiene permisos de escritura
If Permiso = "AMBAS" Or Permiso = "ESCRITURA" Then
    Dim X As Variant, RangoBorrado(0 To 2) As Range
    
    Call InstanciaObjetoBD
    
    Argumentos = Accion & " " & Chr(34) & RutaLibroExcel & Chr(34) & " " _
                 & DatosNombreInterfaz(EsLectura, ThisWorkbook, CAM_TABLA0.ListaProyectoAMS, RangoBorrado(0)) & " " _
                 & DatosTablaInterfaz(EsLectura, ThisWorkbook, CAM_TABLA0.NombreHoja, CAM_TABLA0.Tabla, RangoBorrado(1)) & " " _
                 & DatosNombreInterfaz(Not EsLectura, ThisWorkbook, CAM_AUXILIAR0.MensajeError, RangoBorrado(2)) & " " _
                 & DatosNombreInterfaz(Not EsLectura, ThisWorkbook, CAM_AUXILIAR0.MensajeAdvertenciaUnicodeAMS, RangoBorrado(1)) & " " _
                 & CAM_TABLA0.Tabla & " " _
                 & NombreObjetoTablaBD
    
    For i = 2 To 2
    
        RangoBorrado(i).ClearContents
    
    Next
    
    
    X = Shell(RutaAplicacion + " " + Argumentos, vbMinimizedNoFocus)
Else
    MsgBox "You do not have the necessary permissions to perform this action.", vbExclamation
End If

End Sub

Public Sub TABLA_ELIMINAR_AMS(Accion As String, RutaLibroExcel As String, CAM_TABLA0 As CAMPOS_TABLA, CAM_AUXILIAR0 As CAMPOS_Auxiliar, NombreObjetoTablaBD As String)
Dim Rango As Range
Dim Permiso As String
Set Rango = Hoja6.Range(ClaseNombreBD0.CAM_Auxiliar.HabilitarObjetos)
Permiso = Rango.value
    ' Verificamos si el usuario tiene permisos de escritura
If Permiso = "AMBAS" Or Permiso = "ESCRITURA" Then
    Dim X As Variant, RangoBorrado(0 To 2) As Range
    
    Call InstanciaObjetoBD
    
    Argumentos = Accion & " " & Chr(34) & RutaLibroExcel & Chr(34) & " " _
                 & DatosNombreInterfaz(EsLectura, ThisWorkbook, CAM_TABLA0.ListaProyectoAMS, RangoBorrado(0)) & " " _
                 & DatosTablaInterfaz(EsLectura, ThisWorkbook, CAM_TABLA0.NombreHoja, CAM_TABLA0.Tabla, RangoBorrado(1)) & " " _
                 & DatosNombreInterfaz(Not EsLectura, ThisWorkbook, CAM_AUXILIAR0.MensajeError, RangoBorrado(2)) & " " _
                 & CAM_TABLA0.Tabla & " " _
                 & NombreObjetoTablaBD
    
    For i = 2 To 2
    
        RangoBorrado(i).ClearContents
    
    Next
    
    
    X = Shell(RutaAplicacion + " " + Argumentos, vbMinimizedNoFocus)
Else
    MsgBox "You do not have the necessary permissions to perform this action.", vbExclamation
End If

End Sub


Sub FormatoTituloInterfaz()
    With Range("A1:F1")
        .Merge
        .value = "Panel de Control de Tipologías Constructivas"
        .Font.Name = "Segoe UI"
        .Font.Size = 18
        .Font.Bold = True
        .Font.Color = RGB(255, 255, 255)
        .Interior.Color = RGB(0, 102, 204)
        .HorizontalAlignment = xlCenter
        .VerticalAlignment = xlCenter
        .RowHeight = 30
    End With
End Sub

-------------------------------------------------------------------------------
VBA MACRO Hoja18.cls 