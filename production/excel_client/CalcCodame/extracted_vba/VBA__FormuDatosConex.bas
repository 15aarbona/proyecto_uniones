- - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - 
Private Sub CommandButton1_Click()

If iFilaSelecTabla < UBound(MaFilasSelecTabla) Then
    iFilaSelecTabla = iFilaSelecTabla + 1

    Dim LR0 As ListRow
    Set LR0 = tbl.ListRows(MaFilasSelecTabla(iFilaSelecTabla))
    
    Call EscribeFila(NombresControlesCampos, LR0)
Else
    MsgBox "No hay más registros", vbExclamation

End If

End Sub

Private Sub CommandButton2_Click()

If iFilaSelecTabla > LBound(MaFilasSelecTabla) Then
    iFilaSelecTabla = iFilaSelecTabla - 1

    Dim LR0 As ListRow
    Set LR0 = tbl.ListRows(MaFilasSelecTabla(iFilaSelecTabla))
    
    Call EscribeFila(NombresControlesCampos, LR0)
    
Else
    MsgBox "No hay más registros", vbExclamation

End If

End Sub


Private Sub UserForm_Activate()

Dim AnchoExtra As Integer
Dim AlturaExtra As Integer

    With Me
        ' Activar ambas barras de desplazamiento
        .ScrollBars = fmScrollBarsBoth
        
        AnchoExtra = .Width - .InsideWidth
        
        
        If totalWidth + AnchoExtra > AnchoMaximoFormuDatosConex Then
        
            .Width = AnchoMaximoFormuDatosConex
        
        Else
        
            .Width = totalWidth + AnchoExtra
        
        End If
        
        AlturaExtra = .Height - .InsideHeight
        
        If totalHeight + AlturaExtra > AlturaMaximoFormuDatosConex Then
        
            .Height = AlturaMaximoFormuDatosConex
        
        Else
        
            .Height = totalHeight + AlturaExtra
        
        End If
        
        
        ' Configurar la altura y el ancho de la ventana con scroll
        .ScrollHeight = totalHeight
        .ScrollWidth = totalWidth
        
        
        
        
        
    End With
    
End Sub

Private Sub UserForm_Terminate()

    RangoHojaActiva.Activate
    RangoHojaActiva.Worksheet.Unprotect

End Sub
-------------------------------------------------------------------------------
VBA MACRO Hoja49.cls 