import vtk, qt, ctk, slicer
import os
from slicer.ScriptedLoadableModule import *
import PickAndPaintLogic

class PickAndPaint(ScriptedLoadableModule):
    def __init__(self, parent):
        ScriptedLoadableModule.__init__(self, parent)
        parent.title = "Pick 'n Paint "
        parent.categories = ["Shape Analysis"]
        parent.dependencies = []
        parent.contributors = ["Lucie Macron (University of Michigan), Jean-Baptiste Vimort (University of Michigan)"]
        parent.helpText = """
        Pick 'n Paint tool allows users to select ROIs on a reference model and to propagate it over different time point models.
        """
        parent.acknowledgementText = """
        This work was supported by the National Institues of Dental and Craniofacial Research and Biomedical Imaging and
        Bioengineering of the National Institutes of Health under Award Number R01DE024450
        """
        self.parent = parent

class PickAndPaintWidget(ScriptedLoadableModuleWidget):
    def setup(self):
        print " ----- SetUp ------"
        ScriptedLoadableModuleWidget.setup(self)
        #reload the logic if there is any change
        reload(PickAndPaintLogic)
        self.logic = PickAndPaintLogic.PickAndPaintLogic(self)
        self.interactionNode = slicer.mrmlScene.GetNodeByID("vtkMRMLInteractionNodeSingleton")

        # UI setup
        loader = qt.QUiLoader()
        moduleName = 'PickAndPaint'
        scriptedModulesPath = eval('slicer.modules.%s.path' % moduleName.lower())
        scriptedModulesPath = os.path.dirname(scriptedModulesPath)
        path = os.path.join(scriptedModulesPath, 'Resources', 'UI', '%s.ui' %moduleName)

        qfile = qt.QFile(path)
        qfile.open(qt.QFile.ReadOnly)
        widget = loader.load(qfile, self.parent)
        self.layout = self.parent.layout()
        self.widget = widget
        self.layout.addWidget(widget)

        self.inputModelSelector = self.logic.get("inputModelSelector")
        self.inputModelSelector.setMRMLScene(slicer.mrmlScene)
        self.inputLandmarksSelector = self.logic.get("inputLandmarksSelector")
        self.inputLandmarksSelector.setMRMLScene(slicer.mrmlScene)
        self.loadLandmarksOnSurfacCheckBox = self.logic.get("loadLandmarksOnSurfacCheckBox")
        self.landmarksScaleWidget = self.logic.get("landmarksScaleWidget")
        self.addLandmarksButton = self.logic.get("addLandmarksButton")
        self.surfaceDeplacementCheckBox = self.logic.get("surfaceDeplacementCheckBox")
        self.landmarkComboBox = self.logic.get("landmarkComboBox")
        self.radiusDefinitionWidget = self.logic.get("radiusDefinitionWidget")
        self.cleanerButton = self.logic.get("cleanerButton")
        self.correspondentShapes = self.logic.get("correspondentShapes")
        self.nonCorrespondentShapes = self.logic.get("nonCorrespondentShapes")
        self.propagationInputComboBox = self.logic.get("propagationInputComboBox")
        self.propagationInputComboBox.setMRMLScene(slicer.mrmlScene)
        self.propagateButton = self.logic.get("propagateButton")

        # ------------------------------------------------------------------------------------
        #                                   CONNECTIONS
        # ------------------------------------------------------------------------------------
        self.inputModelSelector.connect('currentNodeChanged(vtkMRMLNode*)', self.onModelChanged)
        self.inputLandmarksSelector.connect('currentNodeChanged(vtkMRMLNode*)', self.onLandmarksChanged)
        self.addLandmarksButton.connect('clicked()', self.onAddButton)
        self.cleanerButton.connect('clicked()', self.onCleanButton)
        self.landmarksScaleWidget.connect('valueChanged(double)', self.onLandmarksScaleChanged)
        self.surfaceDeplacementCheckBox.connect('stateChanged(int)', self.onSurfaceDeplacementStateChanged)
        self.landmarkComboBox.connect('currentIndexChanged(QString)', self.onLandmarkComboBoxChanged)
        self.radiusDefinitionWidget.connect('valueChanged(double)', self.onRadiusValueChanged)
        self.propagationInputComboBox.connect('checkedNodesChanged()', self.onPropagationInputComboBoxCheckedNodesChanged)
        self.propagateButton.connect('clicked()', self.onPropagateButton)


        slicer.mrmlScene.AddObserver(slicer.mrmlScene.EndCloseEvent, self.onCloseScene)

    def enter(self):
        model = self.inputModelSelector.currentNode()
        fidlist = self.inputLandmarksSelector.currentNode()

        if fidlist:
            if fidlist.GetAttribute("connectedModelID") != model.GetID():
                self.inputModelSelector.setCurrentNode(None)
                self.inputLandmarksSelector.setCurrentNode(None)
                self.landmarkComboBox.clear()
        self.UpdateInterface()

    def onCloseScene(self, obj, event):
        list = slicer.mrmlScene.GetNodesByClass("vtkMRMLModelNode")
        end = list.GetNumberOfItems()
        for i in range(0,end):
            model = list.GetItemAsObject(i)
            hardenModel = slicer.mrmlScene.GetNodesByName(model.GetName()).GetItemAsObject(0)
            slicer.mrmlScene.RemoveNode(hardenModel)
        self.radiusDefinitionWidget.value = 0.0
        self.landmarksScaleWidget.value = 2.0
        self.landmarkComboBox.clear()
        self.logic.selectedFidList = None
        self.logic.selectedModel = None

    def UpdateInterface(self):
        if not self.logic.selectedModel:
            return
        activeInput = self.logic.selectedModel
        if not self.logic.selectedFidList:
            return
        fidList = self.logic.selectedFidList
        selectedFidReflID = self.logic.findIDFromLabel(fidList, self.landmarkComboBox.currentText)

        if activeInput:
            # Update values on widgets.
            landmarkDescription = self.logic.decodeJSON(fidList.GetAttribute("landmarkDescription"))
            if landmarkDescription and selectedFidReflID:
                activeDictLandmarkValue = landmarkDescription[selectedFidReflID]
                self.radiusDefinitionWidget.value = activeDictLandmarkValue["ROIradius"]
                if activeDictLandmarkValue["projection"]["isProjected"]:
                    self.surfaceDeplacementCheckBox.setChecked(True)
                else:
                    self.surfaceDeplacementCheckBox.setChecked(False)
            else:
                self.radiusDefinitionWidget.value = 0.0
            self.logic.UpdateThreeDView(self.landmarkComboBox.currentText)


    def onModelChanged(self):
        print "-------Model Changed--------"
        if self.logic.selectedModel:
            Model = self.logic.selectedModel
            try:
                Model.RemoveObserver(self.logic.decodeJSON(self.logic.selectedModel.GetAttribute("modelModifieTagEvent")))
            except:
                pass
        self.logic.selectedModel = self.inputModelSelector.currentNode()
        self.logic.ModelChanged(self.inputModelSelector, self.inputLandmarksSelector)
        self.inputLandmarksSelector.setCurrentNode(None)

    def onLandmarksChanged(self):
        print "-------Landmarks Changed--------"
        if self.inputModelSelector.currentNode():
            self.logic.FidList = self.inputLandmarksSelector.currentNode()
            self.logic.selectedFidList = self.inputLandmarksSelector.currentNode()
            self.logic.selectedModel = self.inputModelSelector.currentNode()
            if self.inputLandmarksSelector.currentNode():
                onSurface = self.loadLandmarksOnSurfacCheckBox.isChecked()
                self.logic.connectLandmarks(self.inputModelSelector,
                                      self.inputLandmarksSelector,
                                      onSurface)
            else:
                self.landmarkComboBox.clear()

    def onAddButton(self):
        # Add fiducial on the scene.
        # If no input model selected, the addition of fiducial shouldn't be possible.
        selectionNode = slicer.mrmlScene.GetNodeByID("vtkMRMLSelectionNodeSingleton")
        selectionNode.SetReferenceActivePlaceNodeClassName("vtkMRMLMarkupsFiducialNode")
        if self.logic.selectedModel:
            if self.logic.selectedFidList:
                selectionNode.SetActivePlaceNodeID(self.logic.selectedFidList.GetID())
                self.interactionNode.SetCurrentInteractionMode(1)
            else:
                self.logic.warningMessage("Please select a fiducial list")
        else:
            self.logic.warningMessage("Please select a model")

    def onLandmarksScaleChanged(self):
        if not self.logic.selectedFidList:
            self.logic.warningMessage("Please select a fiducial list")
            return
        print "------------Landmark scaled change-----------"
        displayFiducialNode = self.logic.selectedFidList.GetMarkupsDisplayNode()
        disabledModify = displayFiducialNode.StartModify()
        displayFiducialNode.SetGlyphScale(self.landmarksScaleWidget.value)
        displayFiducialNode.SetTextScale(self.landmarksScaleWidget.value)
        displayFiducialNode.EndModify(disabledModify)

    def onSurfaceDeplacementStateChanged(self):
        activeInput = self.logic.selectedModel
        if not activeInput:
            return
        fidList = self.logic.selectedFidList
        if not fidList:
            return
        selectedFidReflID = self.logic.findIDFromLabel(fidList, self.landmarkComboBox.currentText)
        isOnSurface = self.surfaceDeplacementCheckBox.isChecked()
        landmarkDescription = self.logic.decodeJSON(fidList.GetAttribute("landmarkDescription"))
        if isOnSurface:
            hardenModel = slicer.app.mrmlScene().GetNodeByID(fidList.GetAttribute("hardenModelID"))
            landmarkDescription[selectedFidReflID]["projection"]["isProjected"] = True
            landmarkDescription[selectedFidReflID]["projection"]["closestPointIndex"] =\
                self.logic.projectOnSurface(hardenModel, fidList, selectedFidReflID)
        else:
            landmarkDescription[selectedFidReflID]["projection"]["isProjected"] = False
            landmarkDescription[selectedFidReflID]["projection"]["closestPointIndex"] = None
            landmarkDescription[selectedFidReflID]["ROIradius"] = 0
        fidList.SetAttribute("landmarkDescription",self.logic.encodeJSON(landmarkDescription))


    def onLandmarkComboBoxChanged(self):
        print "-------- ComboBox changement --------"
        self.UpdateInterface()

    def onRadiusValueChanged(self):
        print "--------- ROI radius modification ----------"
        fidList = self.logic.selectedFidList
        if not fidList:
            return
        selectedFidReflID = self.logic.findIDFromLabel(fidList, self.landmarkComboBox.currentText)
        if selectedFidReflID:
            landmarkDescription = self.logic.decodeJSON(fidList.GetAttribute("landmarkDescription"))
            activeLandmarkState = landmarkDescription[selectedFidReflID]
            activeLandmarkState["ROIradius"] = self.radiusDefinitionWidget.value
            if not activeLandmarkState["projection"]["isProjected"]:
                self.surfaceDeplacementCheckBox.setChecked(True)
                hardenModel = slicer.app.mrmlScene().GetNodeByID(fidList.GetAttribute("hardenModelID"))
                landmarkDescription[selectedFidReflID]["projection"]["isProjected"] = True
                landmarkDescription[selectedFidReflID]["projection"]["closestPointIndex"] =\
                    self.logic.projectOnSurface(hardenModel, fidList, selectedFidReflID)
            fidList.SetAttribute("landmarkDescription",self.logic.encodeJSON(landmarkDescription))
            self.logic.findROI(fidList)

    def onCleanButton(self):
        messageBox = ctk.ctkMessageBox()
        messageBox.setWindowTitle(" /!\ WARNING /!\ ")
        messageBox.setIcon(messageBox.Warning)
        messageBox.setText("Your model is about to be modified")
        messageBox.setInformativeText("Do you want to continue?")
        messageBox.setStandardButtons(messageBox.No | messageBox.Yes)
        choice = messageBox.exec_()
        if choice == messageBox.Yes:
            selectedLandmark = self.landmarkComboBox.currentText
            self.logic.cleanMesh(selectedLandmark)
            self.onRadiusValueChanged()
        else:
            messageBox.setText(" Region not modified")
            messageBox.setStandardButtons(messageBox.Ok)
            messageBox.setInformativeText("")
            messageBox.exec_()

    def onPropagationInputComboBoxCheckedNodesChanged(self):
        if not self.inputModelSelector.currentNode():
            return
        if not self.inputLandmarksSelector.currentNode():
            return
        modelToPropList = self.propagationInputComboBox.checkedNodes()
        finalList = list()
        for model in modelToPropList:
            if model.GetID() != self.inputModelSelector.currentNode().GetID():
                finalList.append(model.GetID())
        self.inputLandmarksSelector.currentNode().SetAttribute("modelToPropList",self.logic.encodeJSON({"modelToPropList":finalList}))

    def onPropagateButton(self):
        print " ------------------------------------ onPropagateButton -------------------------------------- "
        if not self.inputModelSelector.currentNode():
            return
        if not self.inputLandmarksSelector.currentNode():
            return
        model = self.inputModelSelector.currentNode()
        fidList = self.inputLandmarksSelector.currentNode()
        arrayName = fidList.GetAttribute("arrayName")
        modelToPropagateList = self.logic.decodeJSON(fidList.GetAttribute("modelToPropList"))["modelToPropList"]
        for IDmodelToPropagate in modelToPropagateList:
            modelToPropagate = slicer.mrmlScene.GetNodeByID(IDmodelToPropagate)
            isClean = self.logic.decodeJSON(fidList.GetAttribute("isClean"))
            if isClean:
                if not isClean["isClean"]:
                    self.logic.cleanerAndTriangleFilter(modelToPropagate)
                    hardenModel = self.logic.createIntermediateHardenModel(modelToPropagate)
                    modelToPropagate.SetAttribute("hardenModelID",hardenModel.GetID())
            else:
                self.logic.cleanerAndTriangleFilter(modelToPropagate)
                hardenModel = self.logic.createIntermediateHardenModel(modelToPropagate)
                modelToPropagate.SetAttribute("hardenModelID",hardenModel.GetID())
            if self.correspondentShapes.isChecked():
                fidList.SetAttribute("typeOfPropagation","correspondentShapes")
                self.logic.propagateCorrespondent(model, modelToPropagate, arrayName)
            else:
                fidList.SetAttribute("typeOfPropagation","nonCorrespondentShapes")
                self.logic.propagateNonCorrespondent(fidList, modelToPropagate)
        self.UpdateInterface()

class PickAndPaintTest(ScriptedLoadableModuleTest):
    def setUp(self):
        slicer.mrmlScene.Clear(0)

    def runTest(self):
        self.setUp()
        self.delayDisplay(' Starting tests ')

        self.delayDisplay(' Test getClosestPointIndex Function ')
        self.assertTrue(self.testGetClosestPointIndexFunction())

        self.delayDisplay(' Test replaceLandmark Function ')
        self.assertTrue( self.testReplaceLandmarkFunction() )

        self.delayDisplay(' Test DefineNeighbors Function ')
        self.assertTrue( self.testDefineNeighborsFunction() )

        self.delayDisplay(' Test addArrayFromIdList Function ')
        self.assertTrue( self.testAddArrayFromIdListFunction() )

        self.delayDisplay(' Tests Passed! ')


    def testGetClosestPointIndexFunction(self):
        sphereModel = self.defineSphere()
        slicer.mrmlScene.AddNode(sphereModel)
        closestPointIndexList = list()
        polyData = sphereModel.GetPolyData()
        logic = PickAndPaintLogic.PickAndPaintLogic(slicer.modules.PickAndPaintWidget)
        markupsLogic = self.defineMarkupsLogic()


        closestPointIndexList.append(logic.getClosestPointIndex(slicer.mrmlScene.GetNodeByID(markupsLogic.GetActiveListID()),
                                                                polyData,
                                                                0))
        closestPointIndexList.append(logic.getClosestPointIndex(slicer.mrmlScene.GetNodeByID(markupsLogic.GetActiveListID()),
                                                                polyData,
                                                                1))
        closestPointIndexList.append(logic.getClosestPointIndex(slicer.mrmlScene.GetNodeByID(markupsLogic.GetActiveListID()),
                                                                polyData,
                                                                2))

        if closestPointIndexList[0] != 9 or closestPointIndexList[1] != 35 or closestPointIndexList[2] != 1:
            return False
        return True

    def testReplaceLandmarkFunction(self):
        print ' Test replaceLandmark Function '
        logic =  PickAndPaintLogic.PickAndPaintLogic(slicer.modules.PickAndPaintWidget)
        sphereModel = self.defineSphere()
        polyData = sphereModel.GetPolyData()
        markupsLogic = self.defineMarkupsLogic()
        listCoordinates = list()
        listCoordinates.append([55.28383255004883, 55.28383255004883, 62.34897994995117])
        listCoordinates.append([-68.93781280517578, -68.93781280517578, -22.252094268798828])
        listCoordinates.append([0.0, 0.0, -100.0])
        closestPointIndexList = [9, 35, 1]
        coord = [-1, -1, -1]
        for i in range(0, slicer.mrmlScene.GetNodeByID(markupsLogic.GetActiveListID()).GetNumberOfFiducials() ):
            logic.replaceLandmark(polyData, slicer.mrmlScene.GetNodeByID(markupsLogic.GetActiveListID()),
                                  i,
                                  closestPointIndexList[i])
            slicer.mrmlScene.GetNodeByID(markupsLogic.GetActiveListID()).GetNthFiducialPosition(i, coord)
            if coord != listCoordinates[i]:
                print i, ' - Failed '
                return False
            else:
                print i, ' - Passed! '
        return True

    def testDefineNeighborsFunction(self):
        logic = PickAndPaintLogic.PickAndPaintLogic(slicer.modules.PickAndPaintWidget)
        sphereModel = self.defineSphere()
        polyData = sphereModel.GetPolyData()
        closestPointIndexList = [9, 35, 1]
        connectedVerticesReferenceList = list()
        connectedVerticesReferenceList.append([9, 2, 3, 8, 10, 15, 16])
        connectedVerticesReferenceList.append(
            [35, 28, 29, 34, 36, 41, 42, 21, 22, 27, 23, 30, 33, 40, 37, 43, 47, 48, 49])
        connectedVerticesReferenceList.append(
            [1, 7, 13, 19, 25, 31, 37, 43, 49, 6, 48, 12, 18, 24, 30, 36, 42, 5, 47, 41, 11, 17, 23, 29, 35])
        connectedVerticesTestedList = list()

        for i in range(0, 3):
            inter = vtk.vtkIdList()
            logic.defineNeighbor(inter,
                                 polyData,
                                 closestPointIndexList[i],
                                 i + 1)
            connectedVerticesTestedList.append(inter)
            list1 = list()
            for j in range(0, connectedVerticesTestedList[i].GetNumberOfIds()):
                list1.append(int(connectedVerticesTestedList[i].GetId(j)))
            connectedVerticesTestedList[i] = list1
            if connectedVerticesTestedList[i] != connectedVerticesReferenceList[i]:
                print "test ",i ," AddArrayFromIdList: failed"
                return False
            else:
                print "test ",i ," AddArrayFromIdList: succeed"
        return True

    def testAddArrayFromIdListFunction(self):
        logic = PickAndPaintLogic.PickAndPaintLogic(slicer.modules.PickAndPaintWidget)
        sphereModel = self.defineSphere()
        polyData = sphereModel.GetPolyData()
        closestPointIndexList = [9, 35, 1]
        for i in range(0, 3):
            inter = vtk.vtkIdList()
            logic.defineNeighbor(inter, polyData, closestPointIndexList[i], i + 1)
            logic.addArrayFromIdList(inter,
                                     sphereModel,
                                     'Test_' + str(i + 1))
            if polyData.GetPointData().HasArray('Test_' + str(i + 1)) != 1:
                print "test ",i ," AddArrayFromIdList: failed"
                return False
            else:
                print "test ",i ," AddArrayFromIdList: succeed"
        return True

    def defineSphere(self):
        sphereSource = vtk.vtkSphereSource()
        sphereSource.SetRadius(100.0)
        model = slicer.vtkMRMLModelNode()
        model.SetAndObservePolyData(sphereSource.GetOutput())
        modelDisplay = slicer.vtkMRMLModelDisplayNode()
        slicer.mrmlScene.AddNode(modelDisplay)
        model.SetAndObserveDisplayNodeID(modelDisplay.GetID())
        modelDisplay.SetInputPolyDataConnection(sphereSource.GetOutputPort())
        return model

    def defineMarkupsLogic(self):
        slicer.mrmlScene.Clear(0)
        markupsLogic = slicer.modules.markups.logic()
        markupsLogic.AddFiducial(58.602, 41.692, 62.569)
        markupsLogic.AddFiducial(-59.713, -67.347, -19.529)
        markupsLogic.AddFiducial(-10.573, -3.036, -93.381)
        return markupsLogic