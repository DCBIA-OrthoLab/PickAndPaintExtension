import vtk, qt, ctk, slicer
import numpy
import time
from slicer.ScriptedLoadableModule import *


class PickAndPaint(ScriptedLoadableModule):
    def __init__(self, parent):
        ScriptedLoadableModule.__init__(self, parent)
        parent.title = "Pick 'n Paint "
        parent.categories = ["Shape Analysis"]
        parent.dependencies = []
        parent.contributors = ["Lucie Macron (University of Michigan)"]
        parent.helpText = """
        Pick 'n Paint tool allows users to select ROIs on a reference model and to propagate it over different time point models.
        """
        parent.acknowledgementText = """
        This work was supported by the National Institues of Dental and Craniofacial Research and Biomedical Imaging and
        Bioengineering of the National Institutes of Health under Award Number R01DE024450
        """
        self.parent = parent

class PickAndPaintWidget(ScriptedLoadableModuleWidget):
    class landmarkState(object):
        def __init__(self):
            self.landmarkLabel = None
            self.landmarkScale = 2.0
            self.radiusROI = 0.0
            self.indexClosestPoint = -1
            self.arrayName = None
            self.mouvementSurfaceStatus = True
            self.propagatedBool = False

    class inputState (object):
        def __init__(self):
            self.inputModelNode = None
            self.fidNodeID = None
            self.MarkupAddedEventTag = None
            self.PointModifiedEventTag = None
            self.cleanBool = False # if the mesh is cleaned, all the propagated one will be too !
            self.dictionaryLandmark = dict()  # Key: ID of markups
                                              # Value: landmarkState object
            self.dictionaryLandmark.clear()
            # ------------------------- PROPAGATION ------------------------
            self.modelsToPropList = list() # contains ID of Propagated Model Node
            self.propagationType = 0  #  Type of propagation
                                      #  0: No type specified
                                      #  1: Correspondent Shapes
                                      #  2: Non Correspondent Shapes
    def setup(self):
        print " ----- SetUp ------"
        ScriptedLoadableModuleWidget.setup(self)
        # ------------------------------------------------------------------------------------
        #                                   Global Variables
        # ------------------------------------------------------------------------------------
        self.logic = PickAndPaintLogic()
        self.dictionaryInput = dict() # key: ID of the model set as reference
                                      # value: inputState object.
        self.dictionaryInput.clear()
        #-------------------------------------------------------------------------------------
        # Interaction with 3D Scene
        selectionNode = slicer.mrmlScene.GetNodeByID("vtkMRMLSelectionNodeSingleton")
        selectionNode.SetReferenceActivePlaceNodeClassName("vtkMRMLMarkupsFiducialNode")
        self.interactionNode = slicer.mrmlScene.GetNodeByID("vtkMRMLInteractionNodeSingleton")
        
        # ------------------------------------------------------------------------------------
        #                                    Input Selection
        # ------------------------------------------------------------------------------------
        inputLabel = qt.QLabel("Model of Reference: ")
        self.inputModelSelector = slicer.qMRMLNodeComboBox()
        self.inputModelSelector.objectName = 'inputFiducialsNodeSelector'
        self.inputModelSelector.nodeTypes = ['vtkMRMLModelNode']
        self.inputModelSelector.selectNodeUponCreation = False
        self.inputModelSelector.addEnabled = False
        self.inputModelSelector.removeEnabled = False
        self.inputModelSelector.noneEnabled = True
        self.inputModelSelector.showHidden = False
        self.inputModelSelector.showChildNodeTypes = False
        self.inputModelSelector.setMRMLScene(slicer.mrmlScene)

        inputModelSelectorFrame = qt.QFrame(self.parent)
        inputModelSelectorFrame.setLayout(qt.QHBoxLayout())
        inputModelSelectorFrame.layout().addWidget(inputLabel)
        inputModelSelectorFrame.layout().addWidget(self.inputModelSelector)
        #  ------------------------------------------------------------------------------------
        #                                   BUTTONS
        #  ------------------------------------------------------------------------------------
        #  ------------------------------- AddLandmarks Group --------------------------------
        # Landmarks Scale
        self.landmarksScaleWidget = ctk.ctkSliderWidget()
        self.landmarksScaleWidget.singleStep = 0.1
        self.landmarksScaleWidget.minimum = 0.1
        self.landmarksScaleWidget.maximum = 20.0
        self.landmarksScaleWidget.value = 2.0
        landmarksScaleLayout = qt.QFormLayout()
        landmarksScaleLayout.addRow("Scale: ", self.landmarksScaleWidget)

        # Add landmarks Button
        self.addLandmarksButton = qt.QPushButton(" Add ")
        self.addLandmarksButton.enabled = True

        # Movements on the surface
        self.surfaceDeplacementCheckBox = qt.QCheckBox("On Surface")
        self.surfaceDeplacementCheckBox.setChecked(True)

        # Layouts
        scaleAndAddLandmarkLayout = qt.QHBoxLayout()
        scaleAndAddLandmarkLayout.addWidget(self.addLandmarksButton)
        scaleAndAddLandmarkLayout.addLayout(landmarksScaleLayout)
        scaleAndAddLandmarkLayout.addWidget(self.surfaceDeplacementCheckBox)

        # Addlandmarks GroupBox
        addLandmarkBox = qt.QGroupBox()
        addLandmarkBox.title = " Landmarks "
        addLandmarkBox.setLayout(scaleAndAddLandmarkLayout)

        #  ----------------------------------- ROI Group ------------------------------------
        # ROI GroupBox
        self.roiGroupBox = qt.QGroupBox()
        self.roiGroupBox.title = "Region of interest"

        self.landmarkComboBoxROI = qt.QComboBox()

        self.radiusDefinitionWidget = ctk.ctkSliderWidget()
        self.radiusDefinitionWidget.singleStep = 1.0
        self.radiusDefinitionWidget.minimum = 0.0
        self.radiusDefinitionWidget.maximum = 20.0
        self.radiusDefinitionWidget.value = 0.0
        self.radiusDefinitionWidget.tracking = False

        self.cleanerButton = qt.QPushButton('Clean mesh')

        roiBoxLayout = qt.QFormLayout()
        roiBoxLayout.addRow("Select a Landmark:", self.landmarkComboBoxROI)
        HBoxLayout = qt.QHBoxLayout()
        HBoxLayout.addWidget(self.radiusDefinitionWidget)
        HBoxLayout.addWidget(self.cleanerButton)
        roiBoxLayout.addRow("Value of radius", HBoxLayout)
        self.roiGroupBox.setLayout(roiBoxLayout)

        self.ROICollapsibleButton = ctk.ctkCollapsibleButton()
        self.ROICollapsibleButton.setText("Selection Region of Interest: ")
        self.parent.layout().addWidget(self.ROICollapsibleButton)

        ROICollapsibleButtonLayout = qt.QVBoxLayout()
        ROICollapsibleButtonLayout.addWidget(inputModelSelectorFrame)
        ROICollapsibleButtonLayout.addWidget(addLandmarkBox)
        ROICollapsibleButtonLayout.addWidget(self.roiGroupBox)
        self.ROICollapsibleButton.setLayout(ROICollapsibleButtonLayout)

        self.ROICollapsibleButton.checked = True
        self.ROICollapsibleButton.enabled = True

        #  ----------------------------- Propagate Button ----------------------------------
        self.propagationCollapsibleButton = ctk.ctkCollapsibleButton()
        self.propagationCollapsibleButton.setText(" Propagation: ")
        self.parent.layout().addWidget(self.propagationCollapsibleButton)

        self.shapesLayout = qt.QHBoxLayout()
        self.correspondentShapes = qt.QRadioButton('Correspondent Meshes')
        self.correspondentShapes.setChecked(True)
        self.nonCorrespondentShapes = qt.QRadioButton('Non Correspondent Meshes')
        self.nonCorrespondentShapes.setChecked(False)
        self.shapesLayout.addWidget(self.correspondentShapes)
        self.shapesLayout.addWidget(self.nonCorrespondentShapes)

        self.propagationInputComboBox = slicer.qMRMLCheckableNodeComboBox()
        self.propagationInputComboBox.nodeTypes = ['vtkMRMLModelNode']
        self.propagationInputComboBox.setMRMLScene(slicer.mrmlScene)

        self.propagateButton = qt.QPushButton("Propagate")
        self.propagateButton.enabled = True

        propagationBoxLayout = qt.QVBoxLayout()
        propagationBoxLayout.addLayout(self.shapesLayout)
        propagationBoxLayout.addWidget(self.propagationInputComboBox)
        propagationBoxLayout.addWidget(self.propagateButton)

        self.propagationCollapsibleButton.setLayout(propagationBoxLayout)
        self.propagationCollapsibleButton.checked = False
        self.propagationCollapsibleButton.enabled = True

        self.layout.addStretch(1)
        # ------------------------------------------------------------------------------------
        #                                   CONNECTIONS
        # ------------------------------------------------------------------------------------
        self.inputModelSelector.connect('currentNodeChanged(vtkMRMLNode*)', self.onCurrentNodeChanged)
        self.addLandmarksButton.connect('clicked()', self.onAddButton)
        self.cleanerButton.connect('clicked()', self.onCleanButton)
        self.landmarksScaleWidget.connect('valueChanged(double)', self.onLandmarksScaleChanged)
        self.surfaceDeplacementCheckBox.connect('stateChanged(int)', self.onSurfaceDeplacementStateChanged)
        self.landmarkComboBoxROI.connect('currentIndexChanged(QString)', self.onLandmarkComboBoxROIChanged)
        self.radiusDefinitionWidget.connect('valueChanged(double)', self.onRadiusValueChanged)
        self.propagationInputComboBox.connect('checkedNodesChanged()', self.onPropagationInputComboBoxCheckedNodesChanged)
        self.propagateButton.connect('clicked()', self.onPropagateButton)

        def onCloseScene(obj, event):
            # initialize Parameters
            globals()["PickAndPaint"] = slicer.util.reloadScriptedModule("PickAndPaint")
        slicer.mrmlScene.AddObserver(slicer.mrmlScene.EndCloseEvent, onCloseScene)



    def UpdateInterface(self):
        if self.inputModelSelector.currentNode():
            activeInputID = self.inputModelSelector.currentNode().GetID()
            # find the ID of the landmark from its label!
            selectedFidReflID = self.logic.findIDFromLabel(self.dictionaryInput[activeInputID].dictionaryLandmark,
                                                           self.landmarkComboBoxROI.currentText)

            if activeInputID:
                # Update values on widgets.
                if self.dictionaryInput[activeInputID].dictionaryLandmark and selectedFidReflID != False:
                    activeDictLandmarkValue = self.dictionaryInput[activeInputID].dictionaryLandmark[selectedFidReflID]
                    self.landmarksScaleWidget.value = activeDictLandmarkValue.landmarkScale
                    self.radiusDefinitionWidget.value = activeDictLandmarkValue.radiusROI
                    if activeDictLandmarkValue.mouvementSurfaceStatus:
                        self.surfaceDeplacementCheckBox.setChecked(True)
                    else:
                        self.surfaceDeplacementCheckBox.setChecked(False)
                else:
                    self.radiusDefinitionWidget.value = 0.0
                    self.landmarksScaleWidget.value = 2.0
                self.logic.UpdateThreeDView(self.inputModelSelector.currentNode(),
                                            self.dictionaryInput,
                                            self.landmarkComboBoxROI.currentText,
                                            "UpdateInterface")

    def onCurrentNodeChanged(self):
        if self.inputModelSelector.currentNode():
            activeInputID = self.inputModelSelector.currentNode().GetID()
            if activeInputID:
                if not self.dictionaryInput.has_key(activeInputID):
                    # Add the new input on the dictionary
                    self.dictionaryInput[activeInputID] = self.inputState()
                    fidNode  = slicer.vtkMRMLMarkupsFiducialNode()
                    slicer.mrmlScene.AddNode(fidNode)
                    self.dictionaryInput[activeInputID].fidNodeID = fidNode.GetID()

                    # Observers Fiducials Node:
                    self.dictionaryInput[activeInputID].MarkupAddedEventTag = fidNode.AddObserver(fidNode.MarkupAddedEvent, self.onMarkupAddedEvent)
                    self.dictionaryInput[activeInputID].PointModifiedEventTag = fidNode.AddObserver(fidNode.PointModifiedEvent, self.onPointModifiedEvent)
                else:
                    # Key already exists -> Set the markupsList associated to that model active!
                    slicer.modules.markups.logic().SetActiveListID(slicer.mrmlScene.GetNodeByID(self.dictionaryInput[activeInputID].fidNodeID))
                
                # Update landmark ComboBox by adding the labels of landmarks associated to that model
                fidNode = slicer.app.mrmlScene().GetNodeByID(self.dictionaryInput[activeInputID].fidNodeID)
                if fidNode:
                    if self.landmarkComboBoxROI.count != 0:
                        self.landmarkComboBoxROI.clear()
                    numOfFid = fidNode.GetNumberOfMarkups()
                    if numOfFid > 0:
                        for i in range(0, numOfFid):
                            landmarkLabel = fidNode.GetNthMarkupLabel(i)
                            self.landmarkComboBoxROI.addItem(landmarkLabel)

                self.logic.UpdateThreeDView(self.inputModelSelector.currentNode(),
                                            self.dictionaryInput,
                                            self.landmarkComboBoxROI.currentText,
                                            'onCurrentNodeChanged')
            else:
                print ' Input chosen: None! '

    
    def onAddButton(self):
        # Add fiducial on the scene.
        # If no input model selected, the addition of fiducial shouldn't be possible.
        if self.inputModelSelector.currentNode():
            self.interactionNode.SetCurrentInteractionMode(1)
        else:
            messageBox = ctk.ctkMessageBox()
            messageBox.setWindowTitle(" /!\ WARNING /!\ ")
            messageBox.setIcon(messageBox.Warning)
            messageBox.setText("Please select a model of reference")
            messageBox.setStandardButtons(messageBox.Ok)
            messageBox.exec_()


    def onCleanButton(self):
        messageBox = ctk.ctkMessageBox()
        messageBox.setWindowTitle(" /!\ WARNING /!\ ")
        messageBox.setIcon(messageBox.Warning)
        messageBox.setText("Your model is about to be modified")
        messageBox.setInformativeText("Do you want to continue?")
        messageBox.setStandardButtons(messageBox.No | messageBox.Yes )
        choice = messageBox.exec_()

        if choice == messageBox.Yes:
            if self.inputModelSelector.currentNode():
                activeInput = self.inputModelSelector.currentNode()
                self.dictionaryInput[activeInput.GetID()].cleanBool = True

                # Clean the mesh with vtkCleanPolyData cleaner and vtkTriangleFilter:
                self.logic.cleanerAndTriangleFilter(activeInput)

                # Define the new ROI:
                fidNode = slicer.app.mrmlScene().GetNodeByID(self.dictionaryInput[activeInput.GetID()].fidNodeID)
                selectedLandmarkID = self.logic.findIDFromLabel(self.dictionaryInput[activeInput.GetID()].dictionaryLandmark,
                                                                self.landmarkComboBoxROI.currentText)
                if selectedLandmarkID != False:
                    activeLandmarkState = self.dictionaryInput[activeInput.GetID()].dictionaryLandmark[selectedLandmarkID]
                    markupsIndex = fidNode.GetMarkupIndexByID(selectedLandmarkID)
                    activeLandmarkState.indexClosestPoint = self.logic.getClosestPointIndex(fidNode,
                                                                                            slicer.util.getNode(activeInput.GetID()).GetPolyData(),
                                                                                            markupsIndex)
                self.onRadiusValueChanged()
        else:
            messageBox.setText(" Region not modified")
            messageBox.setStandardButtons(messageBox.Ok)
            messageBox.setInformativeText("")
            messageBox.exec_()


    def onLandmarksScaleChanged(self):
        if self.inputModelSelector.currentNode():
            activeInput = self.inputModelSelector.currentNode()
            fidNode = slicer.app.mrmlScene().GetNodeByID(self.dictionaryInput[activeInput.GetID()].fidNodeID)
            if activeInput:
                for value in self.dictionaryInput[activeInput.GetID()].dictionaryLandmark.itervalues():
                    value.landmarkScale = self.landmarksScaleWidget.value
                if fidNode:
                    displayFiducialNode = fidNode.GetMarkupsDisplayNode()
                    disabledModify = displayFiducialNode.StartModify()
                    displayFiducialNode.SetGlyphScale(self.landmarksScaleWidget.value)
                    displayFiducialNode.SetTextScale(self.landmarksScaleWidget.value)
                    displayFiducialNode.EndModify(disabledModify)

                else:
                    print "Error with fiducialNode"

    def onSurfaceDeplacementStateChanged(self):
        print " ------------------------------------ onSurfaceDeplacementStateChanged ------------------------------------"
        if self.inputModelSelector.currentNode():
            activeInput = self.inputModelSelector.currentNode()
            fidNode = slicer.app.mrmlScene().GetNodeByID(self.dictionaryInput[activeInput.GetID()].fidNodeID)

            selectedFidReflID = self.logic.findIDFromLabel(self.dictionaryInput[activeInput.GetID()].dictionaryLandmark,
                                                           self.landmarkComboBoxROI.currentText)
            if selectedFidReflID != False:
                if self.surfaceDeplacementCheckBox.isChecked():
                    self.dictionaryInput[activeInput.GetID()].dictionaryLandmark[selectedFidReflID].mouvementSurfaceStatus = True
                    for key, value in self.dictionaryInput[activeInput.GetID()].dictionaryLandmark.iteritems():
                        markupsIndex = fidNode.GetMarkupIndexByID(key)
                        if value.mouvementSurfaceStatus:
                           value.indexClosestPoint = self.logic.getClosestPointIndex(fidNode,
                                                                                     slicer.util.getNode(activeInput.GetID()).GetPolyData(),
                                                                                     markupsIndex)
                           self.logic.replaceLandmark(slicer.util.getNode(activeInput.GetID()).GetPolyData(),
                                                      fidNode,
                                                      markupsIndex,
                                                      value.indexClosestPoint)
                else:
                    self.dictionaryInput[activeInput.GetID()].dictionaryLandmark[selectedFidReflID].mouvementSurfaceStatus = False


    def onLandmarkComboBoxROIChanged(self):
        print "-------- ComboBox changement --------"
        self.UpdateInterface()

    def onRadiusValueChanged(self):
        print " ------------------------------------ onRadiusValueChanged ---------------------------------------"
        if self.inputModelSelector.currentNode():
            activeInput = self.inputModelSelector.currentNode()
            selectedFidReflID = self.logic.findIDFromLabel(self.dictionaryInput[activeInput.GetID()].dictionaryLandmark,
                                                           self.landmarkComboBoxROI.currentText)
            if selectedFidReflID != False and self.radiusDefinitionWidget.value != 0:
                activeLandmarkState = self.dictionaryInput[activeInput.GetID()].dictionaryLandmark[selectedFidReflID]
                activeLandmarkState.radiusROI = self.radiusDefinitionWidget.value
                if not activeLandmarkState.mouvementSurfaceStatus:
                    self.surfaceDeplacementCheckBox.setChecked(True)
                    activeLandmarkState.mouvementSurfaceStatus = True

                self.radiusDefinitionWidget.setEnabled(False)

                listID = self.logic.defineNeighbor(activeInput.GetPolyData(),
                                                   activeLandmarkState.indexClosestPoint,
                                                   activeLandmarkState.radiusROI)
                self.logic.addArrayFromIdList(listID, activeInput.GetPolyData(), activeLandmarkState.arrayName)
                self.logic.displayROI(activeInput, activeLandmarkState.arrayName)

                # If ROIs has already been propagated: modify the radius on the propagated meshes.
                if self.dictionaryInput[activeInput.GetID()].modelsToPropList:
                    if self.dictionaryInput[activeInput.GetID()].propagationType != 0:
                        if self.dictionaryInput[activeInput.GetID()].propagationType == 1 : # Propagation on correspondent meshes
                            for landmarkState in self.dictionaryInput[activeInput.GetID()].dictionaryLandmark.itervalues():
                                arrayName = landmarkState.arrayName
                                landmarkState.propagatedBool = True
                                for IDModel in self.dictionaryInput[activeInput.GetID()].modelsToPropList:
                                    print IDModel
                                    model = slicer.mrmlScene.GetNodeByID(IDModel)
                                    self.logic.propagateCorrespondent(activeInput, model, arrayName)
                        else:
                            for landmarkID, landmarkState in self.dictionaryInput[activeInput.GetID()].dictionaryLandmark.iteritems():
                                landmarkState.propagatedBool = True
                                for IDModel in self.dictionaryInput[activeInput.GetID()].modelsToPropList:
                                    model = slicer.mrmlScene.GetNodeByID(IDModel)
                                    self.logic.propagateNonCorrespondent(self.dictionaryInput[activeInput.GetID()].fidNodeID,
                                                                         landmarkID,
                                                                         landmarkState,
                                                                         model)
                self.radiusDefinitionWidget.setEnabled(True)
            self.radiusDefinitionWidget.tracking = False

    def onPropagationInputComboBoxCheckedNodesChanged(self):
        if self.inputModelSelector.currentNode():
            activeInputID = self.inputModelSelector.currentNode().GetID()
            del self.dictionaryInput[activeInputID].modelsToPropList[:]
            modelToPropList = self.propagationInputComboBox.checkedNodes()
            for model in modelToPropList:
                if model.GetID() != activeInputID:
                    self.dictionaryInput[activeInputID].modelsToPropList.append(model.GetID())

    def onPropagateButton(self):
        print " ------------------------------------ onPropagateButton -------------------------------------- "
        if self.inputModelSelector.currentNode():
            activeInput = self.inputModelSelector.currentNode()
            if self.correspondentShapes.isChecked():
                self.dictionaryInput[activeInput.GetID()].propagationType = 1
                for landmarkState in self.dictionaryInput[activeInput.GetID()].dictionaryLandmark.itervalues():
                    arrayName = landmarkState.arrayName
                    landmarkState.propagatedBool = True
                    for IDModel in self.dictionaryInput[activeInput.GetID()].modelsToPropList:
                        print IDModel
                        model = slicer.mrmlScene.GetNodeByID(IDModel)
                        if self.dictionaryInput[activeInput.GetID()].cleanBool:
                            self.logic.cleanerAndTriangleFilter(model)
                        self.logic.propagateCorrespondent(activeInput, model, arrayName)
            else:
                self.dictionaryInput[activeInput.GetID()].propagationType = 2
                for landmarkID, landmarkState in self.dictionaryInput[activeInput.GetID()].dictionaryLandmark.iteritems():
                    landmarkState.propagatedBool = True
                    for IDModel in self.dictionaryInput[activeInput.GetID()].modelsToPropList:
                        model = slicer.mrmlScene.GetNodeByID(IDModel)
                        if self.dictionaryInput[activeInput.GetID()].cleanBool:
                            self.logic.cleanerAndTriangleFilter(model)
                        self.logic.propagateNonCorrespondent(self.dictionaryInput[activeInput.GetID()].fidNodeID,
                                                             landmarkID,
                                                             landmarkState,
                                                             model)
            self.UpdateInterface()

    def onMarkupAddedEvent (self, obj, event):
        if self.inputModelSelector.currentNode() != None :
            activeInput = self.inputModelSelector.currentNode()
            numOfMarkups = obj.GetNumberOfMarkups()
            markupID = obj.GetNthMarkupID(numOfMarkups-1)  # because everytime a new node is added, its index is the last one on the list

            self.dictionaryInput[activeInput.GetID()].dictionaryLandmark[markupID] = self.landmarkState()

            landmarkLabel = '  ' + str(numOfMarkups)
            self.dictionaryInput[activeInput.GetID()].dictionaryLandmark[markupID].landmarkLabel = landmarkLabel

            obj.SetNthFiducialLabel(numOfMarkups-1, landmarkLabel)

            arrayName = activeInput.GetName()+ "_ROI_" + str(numOfMarkups)
            self.dictionaryInput[activeInput.GetID()].dictionaryLandmark[markupID].arrayName = arrayName
            self.landmarkComboBoxROI.addItem(landmarkLabel)
            self.landmarkComboBoxROI.setCurrentIndex(self.landmarkComboBoxROI.count-1)

            self.UpdateInterface()

    def onPointModifiedEvent ( self, obj, event):
        if self.inputModelSelector.currentNode():
            activeInput = self.inputModelSelector.currentNode()
            fidNode = slicer.app.mrmlScene().GetNodeByID(self.dictionaryInput[activeInput.GetID()].fidNodeID)
            # remove observer to make sure, the callback function won't work..
            fidNode.RemoveObserver(self.dictionaryInput[activeInput.GetID()].PointModifiedEventTag)
            selectedLandmarkID = self.logic.findIDFromLabel(self.dictionaryInput[activeInput.GetID()].dictionaryLandmark,
                                                            self.landmarkComboBoxROI.currentText)
            if selectedLandmarkID != False:
                activeLandmarkState = self.dictionaryInput[activeInput.GetID()].dictionaryLandmark[selectedLandmarkID]
                markupsIndex = fidNode.GetMarkupIndexByID(selectedLandmarkID)
                if activeLandmarkState.mouvementSurfaceStatus:
                    activeLandmarkState.indexClosestPoint = self.logic.getClosestPointIndex(fidNode,
                                                                                            slicer.util.getNode(activeInput.GetID()).GetPolyData(),
                                                                                            markupsIndex)
                    self.logic.replaceLandmark(slicer.util.getNode(activeInput.GetID()).GetPolyData(),
                                               fidNode,
                                               markupsIndex,
                                               activeLandmarkState.indexClosestPoint)

                # Moving the region if we move the landmark
                if activeLandmarkState.radiusROI > 0 and activeLandmarkState.radiusROI != 0:
                    listID = self.logic.defineNeighbor(activeInput.GetPolyData(),
                                                       activeLandmarkState.indexClosestPoint,
                                                       activeLandmarkState.radiusROI)
                    self.logic.addArrayFromIdList(listID, activeInput.GetPolyData(), activeLandmarkState.arrayName)
                    self.logic.displayROI(activeInput, activeLandmarkState.arrayName)
                    
                    # Moving the region on propagated models if the region has been propagated before      
                    if self.dictionaryInput[activeInput.GetID()].modelsToPropList and activeLandmarkState.propagatedBool:
                        if self.correspondentShapes.isChecked():
                            for nodeID in self.dictionaryInput[activeInput.GetID()].modelsToPropList:
                                node = slicer.mrmlScene.GetNodeByID(nodeID)
                                self.logic.propagateCorrespondent(activeInput, node, activeLandmarkState.arrayName)
                        else:
                            for nodeID in self.dictionaryInput[activeInput.GetID()].modelsToPropList:
                                node = slicer.mrmlScene.GetNodeByID(nodeID)
                                self.logic.propagateNonCorrespondent(self.dictionaryInput[activeInput.GetID()].fidNodeID,
                                                                     selectedLandmarkID,
                                                                     activeLandmarkState,
                                                                     node)
            time.sleep(0.08)
            # Add the observer again
            self.dictionaryInput[activeInput.GetID()].PointModifiedEventTag = fidNode.AddObserver(fidNode.PointModifiedEvent, self.onPointModifiedEvent)

class PickAndPaintLogic(ScriptedLoadableModuleLogic):
    def __init__(self):
        pass
    
    def findIDFromLabel(self, activeInputLandmarkDict, landmarkLabel):
        # find the ID of the markupsNode from the label of a landmark!
        for ID, value in activeInputLandmarkDict.iteritems():
            if value.landmarkLabel == landmarkLabel:
                return ID
        return False

    def cleanerAndTriangleFilter(self, inputNode):
        cleanerPolydata = vtk.vtkCleanPolyData()
        cleanerPolydata.SetInputData(inputNode.GetPolyData())
        cleanerPolydata.Update()
        triangleFilter = vtk.vtkTriangleFilter()
        triangleFilter.SetInputData(cleanerPolydata.GetOutput())
        triangleFilter.Update()
        inputNode.SetAndObservePolyData(triangleFilter.GetOutput())

    def UpdateThreeDView(self, activeInput, dictionaryInput, landmarkLabel = None, functionCaller = None):
        # Update the 3D view on Slicer
        activeInputID = activeInput.GetID()
        if functionCaller == 'onCurrentNodeChanged':
            # On that case: the fiducialNode associated to the activeInput has to be displayed
            for keyInput, valueInput in dictionaryInput.iteritems():
                fidNode = slicer.app.mrmlScene().GetNodeByID(valueInput.fidNodeID)
                if keyInput != activeInputID:
                    if valueInput.dictionaryLandmark:
                        for landID in valueInput.dictionaryLandmark.iterkeys():
                            landmarkIndex = fidNode.GetMarkupIndexByID(landID)
                            fidNode.SetNthFiducialVisibility(landmarkIndex, False)
                else:
                    if valueInput.dictionaryLandmark:
                        for landID in valueInput.dictionaryLandmark.iterkeys():
                            landmarkIndex = fidNode.GetMarkupIndexByID(landID)
                            fidNode.SetNthFiducialVisibility(landmarkIndex, True)

        if functionCaller == 'UpdateInterface' and landmarkLabel:
            selectedFidReflID = self.findIDFromLabel(dictionaryInput[activeInput.GetID()].dictionaryLandmark,
                                                     landmarkLabel)
            fidNode = slicer.app.mrmlScene().GetNodeByID(dictionaryInput[activeInputID].fidNodeID)
            for key in dictionaryInput[activeInputID].dictionaryLandmark.iterkeys():
                markupsIndex = fidNode.GetMarkupIndexByID(key)
                if key != selectedFidReflID:
                    fidNode.SetNthMarkupLocked(markupsIndex, True)
                else:
                    fidNode.SetNthMarkupLocked(markupsIndex, False)
            displayNode = activeInput.GetModelDisplayNode()
            displayNode.SetScalarVisibility(False)
            if dictionaryInput[activeInput.GetID()].modelsToPropList:
                for nodeID in dictionaryInput[activeInput.GetID()].modelsToPropList:
                    node = slicer.mrmlScene.GetNodeByID(nodeID)
                    node.GetDisplayNode().SetScalarVisibility(False)
            if selectedFidReflID != False:
                if dictionaryInput[activeInput.GetID()].dictionaryLandmark[selectedFidReflID].radiusROI > 0:
                    displayNode.SetActiveScalarName(dictionaryInput[activeInput.GetID()].dictionaryLandmark[selectedFidReflID].arrayName)
                    displayNode.SetScalarVisibility(True)
                    for nodeID in dictionaryInput[activeInput.GetID()].modelsToPropList:
                        node = slicer.mrmlScene.GetNodeByID(nodeID)
                        array = node.GetPolyData().GetPointData().GetArray(dictionaryInput[activeInput.GetID()].dictionaryLandmark[selectedFidReflID].arrayName)
                        if array:
                            node.GetDisplayNode().SetActiveScalarName(dictionaryInput[activeInput.GetID()].dictionaryLandmark[selectedFidReflID].arrayName)
                            node.GetDisplayNode().SetScalarVisibility(True)


    def replaceLandmark(self, inputModelPolyData, fidNode, landmarkID, indexClosestPoint):
        landmarkCoord = [-1, -1, -1]
        inputModelPolyData.GetPoints().GetPoint(indexClosestPoint, landmarkCoord)
        fidNode.SetNthFiducialPosition(landmarkID,
                                       landmarkCoord[0],
                                       landmarkCoord[1],
                                       landmarkCoord[2])


    def getClosestPointIndex(self, fidNode,  inputPolyData, landmarkID):
        landmarkCoord = numpy.zeros(3)
        fidNode.GetNthFiducialPosition(landmarkID, landmarkCoord)
        pointLocator = vtk.vtkPointLocator()
        pointLocator.SetDataSet(inputPolyData)
        pointLocator.AutomaticOn()
        pointLocator.BuildLocator()
        indexClosestPoint = pointLocator.FindClosestPoint(landmarkCoord)
        return indexClosestPoint

    def GetConnectedVertices(self, connectedVerticesIDList, polyData, pointID):
        # Return IDs of all the vertices that compose the first neighbor.
        cellList = vtk.vtkIdList()
        connectedVerticesIDList.InsertUniqueId(pointID)
        # Get cells that vertex 'pointID' belongs to
        polyData.GetPointCells(pointID, cellList)
        numberOfIds = cellList.GetNumberOfIds()
        for i in range(0, numberOfIds):
            # Get points which compose all cells
            pointIdList = vtk.vtkIdList()
            polyData.GetCellPoints(cellList.GetId(i), pointIdList)
            for j in range(0, pointIdList.GetNumberOfIds()):
                connectedVerticesIDList.InsertUniqueId(pointIdList.GetId(j))
        return connectedVerticesIDList

    def displayROI(self, inputModelNode, scalarName):
        polyData = inputModelNode.GetPolyData()
        polyData.Modified()
        displayNode = inputModelNode.GetModelDisplayNode()
        disabledModify = displayNode.StartModify()
        displayNode.SetActiveScalarName(scalarName)
        displayNode.SetScalarVisibility(True)
        displayNode.EndModify(disabledModify)

    def addArrayFromIdList(self, connectedIdList, inputModelNodePolydata, arrayName):
        pointData = inputModelNodePolydata.GetPointData()
        numberofIds = connectedIdList.GetNumberOfIds()
        hasArrayInt = pointData.HasArray(arrayName)
        if hasArrayInt == 1:  # ROI Array found
            pointData.RemoveArray(arrayName)
        arrayToAdd = vtk.vtkDoubleArray()
        arrayToAdd.SetName(arrayName)
        for i in range(0, inputModelNodePolydata.GetNumberOfPoints()):
                arrayToAdd.InsertNextValue(0.0)
        for i in range(0, numberofIds):
            arrayToAdd.SetValue(connectedIdList.GetId(i), 1.0)
        lut = vtk.vtkLookupTable()
        tableSize = 2
        lut.SetNumberOfTableValues(tableSize)
        lut.Build()
        lut.SetTableValue(0, 0.0, 0.0, 1.0, 1)
        lut.SetTableValue(1, 1.0, 0.0, 0.0, 1)
        arrayToAdd.SetLookupTable(lut)
        pointData.AddArray(arrayToAdd)
        inputModelNodePolydata.Modified()
        return True

    def defineNeighbor(self, inputModelNodePolyData, indexClosestPoint , distance):
        connectedVerticesList = vtk.vtkIdList()
        connectedVerticesList = self.GetConnectedVertices(connectedVerticesList, inputModelNodePolyData, indexClosestPoint)
        if distance > 1:
            for dist in range(1, int(distance)):
                for i in range(0, connectedVerticesList.GetNumberOfIds()):
                    connectedVerticesList = self.GetConnectedVertices(connectedVerticesList,
                                                                      inputModelNodePolyData,
                                                                      connectedVerticesList.GetId(i))
        return connectedVerticesList

    def propagateCorrespondent(self, referenceInputModel, propagatedInputModel, arrayName):
        referencePointData = referenceInputModel.GetPolyData().GetPointData()
        propagatedPointData = propagatedInputModel.GetPolyData().GetPointData()
        arrayToPropagate = referencePointData.GetArray(arrayName)
        if arrayToPropagate:
            if propagatedPointData.GetArray(arrayName): # Array already exists
                propagatedPointData.RemoveArray(arrayName)
            propagatedPointData.AddArray(arrayToPropagate)
            self.displayROI(propagatedInputModel, arrayName)
        else:
            print " NO ROI ARRAY FOUND. PLEASE DEFINE ONE BEFORE."
            return

    def propagateNonCorrespondent(self, fidNodeID, landmarkID, landmarkState,  propagatedInput):
        fidNode = slicer.app.mrmlScene().GetNodeByID(fidNodeID)
        index = fidNode.GetMarkupIndexByID(landmarkID)
        indexClosestPoint = self.getClosestPointIndex(fidNode, propagatedInput.GetPolyData(), index)
        listID = self.defineNeighbor(propagatedInput.GetPolyData(), indexClosestPoint, landmarkState.radiusROI)
        self.addArrayFromIdList(listID, propagatedInput.GetPolyData(), landmarkState.arrayName)
        self.displayROI(propagatedInput, landmarkState.arrayName)


class PickAndPaintTest(ScriptedLoadableModuleTest):
    def setUp(self):
        slicer.mrmlScene.Clear(0)

    def runTest(self):
        self.delayDisplay("Starting the test")
        
        markupsLogic = slicer.modules.markups.logic()
        markupsLogic.AddFiducial(58.602, 41.692, 62.569)
        markupsLogic.AddFiducial(-59.713, -67.347, -19.529)
        markupsLogic.AddFiducial(-10.573, -3.036, -93.381)
                                                                     
        self.delayDisplay(' Test getClosestPointIndex Function ')
        self.assertTrue( self.testGetClosestPointIndexFunction(markupsLogic) )
        
        self.delayDisplay(' Test replaceLandmark Function ')
        self.assertTrue( self.testReplaceLandmarkFunction(markupsLogic) )


        self.delayDisplay(' Test DefineNeighbors Function ')
        self.assertTrue( self.testDefineNeighborsFunction(markupsLogic) )
    
        self.delayDisplay(' Test addArrayFromIdList Function ')
        self.assertTrue( self.testAddArrayFromIdListFunction(markupsLogic) )
        
        self.delayDisplay(' Tests Passed! ')


    def testGetClosestPointIndexFunction(self, markupsLogic):
        sphereModel = self.defineSphere()
        slicer.mrmlScene.AddNode(sphereModel)
        closestPointIndexList = list()
        polyData = sphereModel.GetPolyData()
        logic = PickAndPaintLogic()
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
    
    def testReplaceLandmarkFunction(self, markupsLogic):
        print ' Test replaceLandmark Function '
        logic = PickAndPaintLogic()
        sphereModel = self.defineSphere()
        polyData = sphereModel.GetPolyData()
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

    def testDefineNeighborsFunction(self, markupsLogic):
        print ' Test DefineNeighbors Function '
        logic = PickAndPaintLogic()
        sphereModel = self.defineSphere()
        polyData = sphereModel.GetPolyData()
        closestPointIndexList = [9, 35, 1]
        connectedVerticesReferenceList = list()
        connectedVerticesReferenceList.append([9, 2, 3, 8, 10, 15, 16])
        connectedVerticesReferenceList.append([35, 28, 29, 34, 36, 41, 42, 21, 22, 27, 23, 30, 33, 40, 37, 43, 47, 48, 49])
        connectedVerticesReferenceList.append([1, 7, 13, 19, 25, 31, 37, 43, 49, 6, 48, 12, 18, 24, 30, 36, 42, 5, 47, 41, 11, 17, 23, 29, 35])
        connectedVerticesTestedList = list()
        
        for i in range(0, slicer.mrmlScene.GetNodeByID(markupsLogic.GetActiveListID()).GetNumberOfFiducials()):
            connectedVerticesTestedList.append(logic.defineNeighbor(polyData,
                                                                    closestPointIndexList[i],
                                                                    i+1))
            list1 = list()
            for j in range(0, connectedVerticesTestedList[i].GetNumberOfIds()):
                list1.append(int(connectedVerticesTestedList[i].GetId(j)))
            connectedVerticesTestedList[i] = list1
            if connectedVerticesTestedList[i] != connectedVerticesReferenceList[i]:
                print i, " - Failed! "
                return False
            else:
                print i, " - Passed! "
    
        return True
        
    def testAddArrayFromIdListFunction(self, markupsLogic):
        print ' Test AddArrayFromIdList Function '
        logic = PickAndPaintLogic()
        sphereModel = self.defineSphere()
        polyData = sphereModel.GetPolyData()
        closestPointIndexList = [9, 35, 1]
        for i in range(0, slicer.mrmlScene.GetNodeByID(markupsLogic.GetActiveListID()).GetNumberOfFiducials()):
            logic.addArrayFromIdList(logic.defineNeighbor(polyData, closestPointIndexList[i], i+1),
                                     polyData,
                                     'Test_'+str(i+1))
            if polyData.GetPointData().HasArray('Test_'+str(i+1)) != 1:
                print i, "Failed! "
                return False
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


