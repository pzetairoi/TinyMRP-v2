Attribute VB_Name = "HideSketchesExample1"
Option Explicit
Dim colCompList As New Collection
Dim colComponents As New Collection
Dim colFeatures As New Collection
Dim SelFilter As Long
Public allConfigCheck As Boolean

Sub BlankFeaturesInCollection(inCol As Collection, inDoc As SldWorks.ModelDoc2)
    If inCol.Count = 0 Or inDoc Is Nothing Then Exit Sub
    
    'Dim bfSelMgr As SldWorks.SelectionMgr
    Dim bfFeat As SldWorks.Feature
    Dim c As Long 'counter
    Dim bfAppend As Boolean
    
    'get selection manager
    'Set bfSelMgr = inDoc.SelectionManager
    
    c = 0
    bfAppend = False
    
    For Each bfFeat In inCol
        c = c + 1
        bfFeat.Select2 bfAppend, 0
        bfAppend = True
        If c / 25 = Int(c / 25) Then
            inDoc.BlankRefGeom
            inDoc.BlankSketch
            bfAppend = False
        End If
    Next
    inDoc.BlankRefGeom
    inDoc.BlankSketch
    
    'select and deselect single feature to clear selections
    For Each bfFeat In inCol
        bfFeat.Select2 False, 0
        bfFeat.DeSelect
        Exit For
    Next
    
    Set bfFeat = Nothing

End Sub

Sub EmptyCollection(inCol As Collection)
    If inCol Is Nothing Then Exit Sub
    
    Dim i As Long
    For i = 1 To inCol.Count
        inCol.Remove (1)
    Next

End Sub
Function FeatureTypeValue(inTypeName As String) As Long
Select Case inTypeName
    Case "OriginProfileFeature"
        FeatureTypeValue = 1
    Case "RefPlane"
        FeatureTypeValue = 2
    Case "RefAxis"
        FeatureTypeValue = 4
    Case "RefPoint"
        FeatureTypeValue = 8
    Case "CoordSys"
        FeatureTypeValue = 16
    Case "ProfileFeature" '2D sketch
        FeatureTypeValue = 32
    Case "3DProfileFeature" '3D sketch
        FeatureTypeValue = 64
    Case "3DSplineCurve" 'curve thru points
        FeatureTypeValue = 128
    Case "CompositeCurve"
        FeatureTypeValue = 256
    Case "Helix"
        FeatureTypeValue = 512
    Case Else
        FeatureTypeValue = 0
End Select
        
End Function

Function TestFeatureType(inFeat As SldWorks.Feature) As Boolean
Dim ft As String
ft = inFeat.GetTypeName
'If ft = "OriginProfileFeature" Or _
    ft = "ProfileFeature" Or _
    ft = "RefAxis" Or _
    ft = "CoordSys" Or _
    ft = "RefPoint" Or _
    ft = "RefPlane" Or _
    ft = "CompositeCurve" Or _
    ft = "3DSplineCurve" Or _
    ft = "Helix" Or _
    ft = "3DProfileFeature" _
Then

If SelFilter And FeatureTypeValue(ft) Then
    TestFeatureType = True
Else
    TestFeatureType = False
End If

End Function

Sub AddFeatureToCollection(inFeature As SldWorks.Feature, inCol As Collection)
    Dim nFeat As SldWorks.Feature
    Set nFeat = inFeature
    inCol.Add nFeat
    Set nFeat = Nothing
End Sub

Function HandleInCollection(inHandle As String, inCol As Collection) As Boolean

    If inCol Is Nothing Then GoTo hicError
    On Error Resume Next
    
    Dim hicCheckString As String
    Dim hicCheckObject As Object
    
    hicCheckString = inCol.Item(inHandle)
    Set hicCheckObject = inCol.Item(inHandle)
    
    If hicCheckString = "" And hicCheckObject Is Nothing Then GoTo hicError
    
    HandleInCollection = True
    Set hicCheckObject = Nothing
    Exit Function
    
hicError:
    Set hicCheckObject = Nothing
    HandleInCollection = False
End Function

Function mCompModelDoc(inComp As SldWorks.Component2) As ModelDoc2
    If inComp Is Nothing Then Exit Function
    Set mCompModelDoc = inComp.GetModelDoc
End Function

Function mComponentTag(inComp As SldWorks.Component2) As String
    If inComp Is Nothing Then Exit Function
    mComponentTag = mFileName(mCompModelDoc(inComp)) & _
        "||" & _
        inComp.ReferencedConfiguration
End Function

Function mdAsm(inDoc As SldWorks.ModelDoc2) As SldWorks.AssemblyDoc
    
End Function
Function mDocPath(inDoc As SldWorks.ModelDoc2) As String
    If inDoc Is Nothing Then mDocPath = "": Exit Function
    mDocPath = inDoc.GetPathName
End Function

Function mFileName(inDoc As SldWorks.ModelDoc2) As String
    Dim s As String
    Dim i As Long
    
    If inDoc Is Nothing Then mFileName = "": Exit Function
    s = inDoc.GetPathName
    For i = Len(s) To 1 Step -1
        If Mid(s, i, 1) = "\" Or Mid(s, i, 1) = "/" Then Exit For
    Next
    
    mFileName = Right(s, Len(s) - i)

End Function

Function mDocTitle(inDoc As SldWorks.ModelDoc2) As String
    mDocTitle = inDoc.GetTitle
End Function
Function mDocType(inDoc As SldWorks.ModelDoc2) As Long
    On Error Resume Next
    mDocType = 0
    mDocType = inDoc.GetType
End Function

Sub BlankRefFeatures( _
    swApp As SldWorks.SldWorks, _
    swModel As SldWorks.ModelDoc2, _
    swFeat As SldWorks.Feature)
    
    If Not TestFeatureType(swFeat) Then Exit Sub
    
    swFeat.Select2 False, 0
    swModel.BlankRefGeom
    swModel.BlankSketch
    swFeat.DeSelect

End Sub

 
Sub TraverseFeatureFeatures( _
    swApp As SldWorks.SldWorks, _
    swModel As SldWorks.ModelDoc2, _
    swFeat As SldWorks.Feature, _
    inFeatCol As Collection, _
    nLevel As Long)
    
If swApp Is Nothing Or swModel Is Nothing Or swFeat Is Nothing Then
    'Debug.Print "TraverseFeatureFeatures: passed empty SW object " & Now
    Exit Sub
End If

Dim swSubFeat                   As SldWorks.Feature

Dim swSubSubFeat                As SldWorks.Feature

Dim swSubSubSubFeat             As SldWorks.Feature

Dim sPadStr                     As String

Dim i                           As Long

    

    For i = 0 To nLevel

        sPadStr = sPadStr + "  "

    Next i

    

    Dim bRet As Boolean

    

    If "Annotations" <> swFeat.Name Then

        bRet = swFeat.Select2(True, 0) ': Debug.Assert bRet

    End If

    While Not swFeat Is Nothing
        'debug.print sPadStr + swFeat.Name + " [" + swFeat.GetTypeName + "]"
        'BlankRefFeatures swApp, swModel, swFeat
        If TestFeatureType(swFeat) And (swFeat.Visible = swVisibilityStateShown Or swFeat.Visible = swVisibilityStateUnknown) Then AddFeatureToCollection swFeat, inFeatCol
        
        Set swSubFeat = swFeat.GetFirstSubFeature
        While Not swSubFeat Is Nothing
            'debug.print sPadStr + "  " + swSubFeat.Name + " [" + swSubFeat.GetTypeName + "]"
            'BlankRefFeatures swApp, swModel, swSubFeat
            If TestFeatureType(swSubFeat) And (swSubFeat.Visible = swVisibilityStateShown Or swSubFeat.Visible = swVisibilityStateUnknown) Then AddFeatureToCollection swSubFeat, inFeatCol
            
            Set swSubSubFeat = swSubFeat.GetFirstSubFeature
            While Not swSubSubFeat Is Nothing
                'debug.print sPadStr + "    " + swSubSubFeat.Name + " [" + swSubSubFeat.GetTypeName + "]"
                'BlankRefFeatures swApp, swModel, swSubSubFeat
                If TestFeatureType(swSubSubFeat) And (swSubSubFeat.Visible = swVisibilityStateShown Or swSubSubFeat.Visible = swVisibilityStateUnknown) Then AddFeatureToCollection swSubSubFeat, inFeatCol
                
                Set swSubSubSubFeat = swSubFeat.GetFirstSubFeature
                While Not swSubSubSubFeat Is Nothing
                    'debug.print sPadStr + "      " + swSubSubSubFeat.Name + " [" + swSubSubSubFeat.GetTypeName + "]"
                    'BlankRefFeatures swApp, swModel, swSubSubSubFeat
                    If TestFeatureType(swSubSubSubFeat) And (swSubSubSubFeat.Visible = swVisibilityStateShown Or swSubSubSubFeat.Visible = swVisibilityStateUnknown) Then AddFeatureToCollection swSubSubSubFeat, inFeatCol

                    Set swSubSubSubFeat = swSubSubSubFeat.GetNextSubFeature()
                Wend
                
                Set swSubSubFeat = swSubSubFeat.GetNextSubFeature()
            Wend

            Set swSubFeat = swSubFeat.GetNextSubFeature()
        Wend

        Set swFeat = swFeat.GetNextFeature
    Wend
    
    
    Set swSubFeat = Nothing                  'SldWorks.Feature
    Set swSubSubFeat = Nothing               'SldWorks.Feature
    Set swSubSubSubFeat = Nothing            'SldWorks.Feature
End Sub

Sub TraverseComponentFeatures( _
    swApp As SldWorks.SldWorks, _
    swModel As SldWorks.ModelDoc2, _
    swComp As SldWorks.Component2, _
    inFeatCol As Collection, _
    nLevel As Long)

    Dim swFeat As SldWorks.Feature
    
    Set swFeat = swComp.FirstFeature
    
    TraverseFeatureFeatures swApp, swModel, swFeat, inFeatCol, nLevel
    
    Set swFeat = Nothing

End Sub

 

Sub TraverseComponent( _
    swApp As SldWorks.SldWorks, _
    swModel As SldWorks.ModelDoc2, _
    swComp As SldWorks.Component2, _
    nLevel As Long)

    Dim vChildComp                  As Variant
    Dim swChildComp                 As SldWorks.Component2
    Dim swCompConfig                As SldWorks.Configuration
    Dim sPadStr                     As String
    Dim i                           As Long

    For i = 0 To nLevel - 1
        sPadStr = sPadStr + "  "
    Next i

vChildComp = swComp.GetChildren

For i = 0 To UBound(vChildComp)

    Set swChildComp = vChildComp(i)

    

    'debug.print sPadStr & "+" & swChildComp.Name2 & " <" & swChildComp.ReferencedConfiguration & ">"

    
'check if doc has been done before traversing features
    If Not HandleInCollection(mComponentTag(swChildComp), colCompList) Then
        If mComponentTag(swChildComp) <> "" Then
            colComponents.Add swChildComp, mComponentTag(swChildComp)
            colCompList.Add mComponentTag(swChildComp), mComponentTag(swChildComp)
        End If
        'Debug.Print "Add " & mFileName(mCompModelDoc(swChildComp))
        'TraverseComponentFeatures swApp, swModel, swChildComp, nLevel
    Else
        'Debug.Print "Skip " & mFileName(mCompModelDoc(swChildComp))
    End If

    TraverseComponent swApp, swModel, swChildComp, nLevel + 1
    Set swChildComp = Nothing '               As SldWorks.Component2
    Set swCompConfig = Nothing  '            As SldWorks.Configuration

Next i

Set swChildComp = Nothing '               As SldWorks.Component2
Set swCompConfig = Nothing  '            As SldWorks.Configuration
vChildComp = Null

End Sub

 

Sub TraverseModelFeatures( _
    swApp As SldWorks.SldWorks, _
    swModel As SldWorks.ModelDoc2, _
    inFeatCol As Collection, _
    nLevel As Long)

    Dim swFeat                      As SldWorks.Feature

    

    Set swFeat = swModel.FirstFeature

    TraverseFeatureFeatures swApp, swModel, swFeat, inFeatCol, nLevel
    
Set swFeat = Nothing

End Sub

 
 Sub AssemblyTraverseProcess(swApp As SldWorks.SldWorks, swModel As SldWorks.ModelDoc2, swRootComp As SldWorks.Component2, swConf As SldWorks.Configuration)
     Set swRootComp = swConf.GetRootComponent
    
    'debug.print "File = " & swModel.GetPathName
    
    TraverseModelFeatures swApp, swModel, colFeatures, 1
    BlankFeaturesInCollection colFeatures, swModel
    
    TraverseComponent swApp, swModel, swRootComp, 1 'gathers components in colComponents
    
    Dim ccComp As SldWorks.Component2
    Dim ccC As Long
    ccC = 0
    
    EmptyCollection colFeatures
    
    For Each ccComp In colComponents
        ccC = ccC + 1
        'EmptyCollection colFeatures
        TraverseComponentFeatures swApp, mCompModelDoc(ccComp), ccComp, colFeatures, 1
        'BlankFeaturesInCollection colFeatures, mCompModelDoc(ccComp)
        'BlankFeaturesInCollection colFeatures, swModel
        'Debug.Print "Blank " & ccComp.Name2
    Next
    
    Set ccComp = Nothing
 End Sub
 

Sub main()

    Load frmFeatureSelection
    frmFeatureSelection.InitValues
    SelFilter = frmFeatureSelection.SelectSum
    If Not frmFeatureSelection.OKFlag Then Unload frmFeatureSelection: End
    Unload frmFeatureSelection

    'Debug.Print
    'Debug.Print "Start " & Now
    
        Dim swApp                       As SldWorks.SldWorks
        Dim swModel                     As SldWorks.ModelDoc2
        Dim swConf                      As SldWorks.Configuration
        Dim swRootComp                  As SldWorks.Component2
        Dim nStart                      As Single
        Dim bRet                        As Boolean
        Dim vConfNameArr                As Variant
        Dim sConfigName                 As String
        Dim bShowConfig                 As Boolean
        Dim i                           As Integer
        Dim myTime As Date
        Dim TotalTime As Double
        Dim modView As ModelView
      
    EmptyCollection colComponents
    EmptyCollection colFeatures
    EmptyCollection colCompList
    
        Set swApp = Application.SldWorks
        Set swModel = swApp.ActiveDoc
        Set modView = swModel.ActiveView
        Set swConf = swModel.GetActiveConfiguration
        vConfNameArr = swModel.GetConfigurationNames
        
    myTime = Time
    modView.EnableGraphicsUpdate = False
    swModel.FeatureManager.EnableFeatureTree = False
    '=============================
    'start PART
    '=============================
    If mDocType(swModel) = 1 Then
        If allConfigCheck = True Then
            For i = 0 To UBound(vConfNameArr)
                sConfigName = vConfNameArr(i)
                bShowConfig = swModel.ShowConfiguration2(sConfigName)
                
                TraverseModelFeatures swApp, swModel, colFeatures, 0
                BlankFeaturesInCollection colFeatures, swModel
            Next i
        Else
            TraverseModelFeatures swApp, swModel, colFeatures, 0
            BlankFeaturesInCollection colFeatures, swModel
        End If
        
        GoTo ExitStrategy
    End If
    '=============================
    'end PART
    '=============================
    
    If mDocType(swModel) <> 2 Then GoTo ExitStrategy
    
    '=============================
    'start ASSEMBLY
    '=============================
    
    nStart = Timer
    
    If allConfigCheck = True Then
        For i = 0 To UBound(vConfNameArr)
            sConfigName = vConfNameArr(i)
            bShowConfig = swModel.ShowConfiguration2(sConfigName)
            
            AssemblyTraverseProcess swApp, swModel, swRootComp, swConf
        Next i
    Else
        AssemblyTraverseProcess swApp, swModel, swRootComp, swConf
    End If
    
    BlankFeaturesInCollection colFeatures, swModel
    
        'debug.print ""
        'debug.print "Time = " & Timer - nStart & " s"
    '=============================
    'end ASSEMBLY
    '=============================
    
ExitStrategy:
    Set swRootComp = Nothing                 'SldWorks.Component2
    Set swConf = Nothing                     'SldWorks.Configuration
    
    EmptyCollection colCompList
    EmptyCollection colComponents
    EmptyCollection colFeatures
    
    modView.EnableGraphicsUpdate = True
    swModel.FeatureManager.EnableFeatureTree = True
    'Debug.Print "Finish " & Now
    'Debug.Print
    TotalTime = DateDiff("s", myTime, Time)
    MsgBox "Completion time: " & TotalTime & " seconds"
End Sub

