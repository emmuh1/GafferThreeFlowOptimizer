# Copyright (c) 2012 The Foundry Visionmongers Ltd. All Rights Reserved.

from Katana import QtCore, QtGui, UI4, QT4Widgets, QT4FormWidgets
from Katana import NodegraphAPI, Utils, Nodes3DAPI, FnGeolib
from Katana import UniqueName, FormMaster, Utils
from PyQt4 import QtCore, QtGui
import settings, os, math, csv

'''
SuperTool --> group (shot/sequence) 
            --> block --> group (key/shot) [shot] --> block/shots --> LG --> Gaffer
PUBLISH | GAFFER.. | KEY.. | SHOT.. | BLOCK (key+shot) | MASTER..
KEY: Group that holds gaffers
SHOT: Group that holds groups (Shots/SubGroups)
MASTER: Top most group

To Do:
    1.) Publish BLOCKS
    2.) Delete/Disable ShotBrowserItems (incase of duplication)
    3.) Default column width of sequence to 0 (so that default is for users
            leads/sequence peeps can expand it...)
            - not really sure how permissions would work...
                edit flag
                    show/disable ShotBrowser
                hotkey to popup shot changer
                
    

BUGS:
    1.) shot publish versions not displaying correct version..
    
    2.) Drag/Drop in ShotBrowser is doing odd re-ordering
            -- Currently can't replicate this?
            self.current_parent... appears to be the culprit? selecting the last node over...
                vs
            the curren    gaffert items parent after drop?
            
    3.) Drag/Drop Groups w/items inside creates secondary port?
            -- Currently can't replicate
    4.) 1708 breaking on 3rd drop of node into shot group
    
    5.) If no shots, wont create a Block (Group)
    6.) 1712(1713) list index out of range?
    7.) Can drop at top most level
WISH LIST:
    1.) Import/Export?
    2.) Disabled Functions for different users
    3.) Drag/Drop nodes into LG?
    4.) Change 'master' name to <sequence name>
    5.) Expose %s to shot/master/creation dirs... so that it can be easily added into a pipeline
        for custom save directories
    6.) Show version of live/greatest (filters by these versions?)
'''
class GafferThreeSequenceEditor(QtGui.QWidget):
    
    def __init__(self, parent, node):
        
        def initDefaultAttributes():
            #=======================================================================
            # renitializes default attributes on the node, so that they can be recalled
            #=======================================================================
            self.node = node
            self.node.__init__(populate=False)
            self.sequence = self.node.getParameter('sequence').getValue(0)
            #self.shot = self.node.getParameter('shot').getValue(0)
            self.shot = None
            self.shot_list = self.setShotList()
        
        def createGUI():

            QtGui.QGridLayout(self)

            self.sequence_cb = self.createValueParam('sequence')
            self.publish_dir = self.createValueParam('publish_dir')

            self.gaffer_display = self.createValueParam('gaffer_display')
            self.gaffer_stack = self.createGafferThreeStack()
            
            #### Creates a fake parameter policy (thanks Dan =P) 
            policyData = dict(displayNode="")
            rootPolicy = QT4FormWidgets.PythonValuePolicy("cels", policyData)
            self.params_policy = rootPolicy.getChildByName("displayNode")
            self.params_policy.getWidgetHints().update(widget='teleparam',  open="True",hideTitle = "True")
            self.params = UI4.FormMaster.KatanaWidgetFactory.buildWidget(None, self.params_policy)
    
            self.splitter = QtGui.QSplitter()
            self.splitter.addWidget(self.gaffer_stack)
    
            self.splitter.addWidget(self.params)
            
            self.scroll = QtGui.QScrollArea()
            self.scroll.setWidget(self.params)
            self.scroll.setWidgetResizable(True)
            self.splitter.addWidget(self.scroll)
            self.splitter.setSizes([200,600])
            self.splitter.setFixedHeight(500)
            #self.splitter.resize(self.splitter.sizeHint().width(),5000)
            '''
            #=======================================================================
            # hacky hacky getting it to stretch?
            #=======================================================================
            self.vsplitter = QtGui.QSplitter(QtCore.Qt.Vertical)
            label = QtGui.QWidget()
            label.setFixedHeight(1500)
            self.vsplitter.addWidget(self.splitter)
            self.vsplitter.addWidget(label)
            
            self.__treeStretchBox = UI4.Widgets.StretchBox(self,allowHorizontal=False, allowVertical=True)
            self.layout().addWidget(self.__treeStretchBox)
    
            self.__treeWidget = QT4Widgets.SortableTreeWidget(self.__treeStretchBox)
            '''
    
            ### Set QT Layout
            self.layout().addWidget(self.publish_dir          ,0,2,1,8)
            
            self.layout().addWidget(self.sequence_cb            ,0,0,1,2)
            self.layout().addWidget(self.splitter               ,2,0,1,10)

            try:
                self.updateShotGaffer()
            except:
                pass
            
        def checkGSV():
            def addGlobalGraphStateVariable(name):
                variablesGroup = NodegraphAPI.GetRootNode().getParameter('variables')
                variableParam = variablesGroup.createChildGroup(name)
                variableParam.createChildNumber('enable', 1)
                variableParam.createChildString('value', '')
                return variableParam.getName()
            
            root = NodegraphAPI.GetRootNode()
            if not root.getParameter('variables.shot'):
                addGlobalGraphStateVariable('shot')
            if not root.getParameter('variables.sequence'):
                addGlobalGraphStateVariable('sequence')

        QtGui.QWidget.__init__(self, parent)
        
        initDefaultAttributes()
        checkGSV()
        createGUI()
        self.item_list = None
        #Utils.EventModule.RegisterCollapsedHandler(self.updateSequence, 'parameter_finalizeValue',None)
        
        Utils.EventModule.RegisterCollapsedHandler(self.paramChanged, 'parameter_finalizeValue',None)
        
    def paramChanged(self,args):
        #=======================================================================
        # looks for parameters being changed that pertaining to this node
        # GSV --> shot | sequence
        # GTFO --> publish_dir
        #=======================================================================
        def changeShot(args):
            param = args[2][2]['param']
            param_name = param.getParent().getName()
            shot = param.getValue(0)
            if param_name not in self.shot_list:
                master_item = self.shot_browser.topLevelItem(0)
                master_item_shots_group = NodegraphAPI.GetNode(master_item.getRootNode().getParameter('nodeReference.shot_group').getValue(0))
                shot_group_node = self.node.createShotGroup(root_node=master_item_shots_group,shot=shot)
                unique_hash = shot_group_node.getChildByIndex(0).getParameter('hash').getValue(0)
                item = ShotBrowserItem(master_item,root_node=shot_group_node,shot_node=shot_group_node.getChildByIndex(0), \
                                       key_node=shot_group_node.getChildByIndex(0),unique_hash = unique_hash ,\
                                       name=shot,item_type='shot')

                if len(master_item_shots_group.getChildren()) == 0:
                    previous_port = master_item_shots_group.getSendPort('in')
                else:
                    #previous_port = master_item.child(master_item.childCount()-1).getRootNode().getOutputPortByIndex(0)
                    previous_port = master_item_shots_group.getChildByIndex(len(master_item_shots_group.getChildren())-2).getOutputPortByIndex(0)
                
                #Create Nodes
                last_node = master_item_shots_group.getChildByIndex(len(master_item_shots_group.getChildren())-1)
                #Connect Nodes'
                previous_port.connect(shot_group_node.getInputPortByIndex(0))
                shot_group_node.getOutputPortByIndex(0).connect(master_item_shots_group.getReturnPort('out'))
                #Position Nodes
                current_pos = NodegraphAPI.GetNodePosition(last_node)
                new_pos = (current_pos[0],current_pos[1]-100)
                NodegraphAPI.SetNodePosition(shot_group_node, new_pos)
                self.setShotList()
                
        def changeDirectory(args):
            #=======================================================================
            # checks to see if the user has changed a parameter that would adjust which sequence gaffer is used
            # loads that gaffer livegroup in
            #=======================================================================
            def createDirectories():
                #===============================================================
                # creates all necessary directories / subdirectories
                #===============================================================
                dir_list = [publish_dir , sequence_dir , sequence_dir + '/blocks' ,  sequence_dir + '/shots']
                for dir_item in dir_list:
                    if not os.path.exists(dir_item):
                        os.mkdir(dir_item)
                master_item = self.shot_browser.topLevelItem(0)
                self.item_list = [master_item]
                self.getItemList(master_item)
                dir_list = ['gaffers','key','live_group','publish']
                for item in self.item_list:
                    unique_hash = item.getHash()
                    if item.getItemType() == 'block':
                        #unique_hash = item.getHash()
                        item_type = 'blocks'
                    elif item.getItemType() in ['shot','master']:
                        #unique_hash = item.getHash()
                        #=======================================================
                        # kinda hacky thing to seperate shot from master item type... should just replace this?
                        #=======================================================
                        if item.getItemType() == 'shot':
                            unique_hash = '%s_%s'%(self.getSequence() , unique_hash[unique_hash.rindex('_')+1:])
                            item.getKeyNode().getParameter('hash').setValue(unique_hash,0)
                        item.setHash(unique_hash)
                        
                        item_type = 'shots'
                    item_dir = '%s/%s/%s'%(sequence_dir,item_type,unique_hash)
                    os.mkdir(item_dir)
                    item.setPublishDir(item_dir)
                    for dir_item in dir_list:
                        if not os.path.exists(item_dir + '/%s'%dir_item):
                            os.mkdir(item_dir + '/%s'%dir_item)
                            os.mkdir(item_dir + '/%s/live'%dir_item)
                    
                    #===========================================================
                    # populate key gaffers
                    #===========================================================

                    gaffers_dir = item_dir + '/gaffers'
                    key_node = item.getKeyNode()
                    for child in key_node.getParameter('nodeReference').getChildren():
                        node = NodegraphAPI.GetNode(child.getValue(0))
                        unique_hash = node.getParameter('hash').getValue(0)
                        new_dir = '%s/%s'%(gaffers_dir,unique_hash)
                        if not os.path.exists(new_dir):
                            os.mkdir(new_dir)
                            os.mkdir(new_dir + '/live')

            publish_dir = self.node.getParameter('publish_dir').getValue(0)
            sequence_dir = '%s/%s'%(publish_dir,self.getSequence())
            if not os.path.exists(sequence_dir):
                warning_message = QtGui.QMessageBox()
                warning_message.setInformativeText('Create Directories?')
                warning_message.setStandardButtons(QtGui.QMessageBox.Ok | QtGui.QMessageBox.Cancel)
                retval = warning_message.exec_()
                if retval == 1024:
                    createDirectories()
                elif retval == 4194304:
                    'not okie'
            else:

                master_item = self.shot_browser.topLevelItem(0)
                master_dir = sequence_dir + '/shots/master/live_group'
                if os.path.exists(master_dir +'/live/gaffer.livegroup'):

                    version='live'
                else:            
                    versions = os.listdir(master_dir)
                    versions.remove('live')
                    if len(versions) == 0:
                        createDirectories()
                    else:
                        version = sorted(versions)[-1]

                self.setWorkingItem(master_item)
                self.loadLiveGroup(None,2,version=version)

        #=======================================================================
        # GSV 'shot' changed
        # create new item in group
        #=======================================================================
        def updateSequence(args,param):
            self.setSequence(param.getValue(0))
            changeDirectory(args)

        #=======================================================================
        # args[2][2] is for a new creation of a parameter... if it is in the args[0][2] position
        # then it is refering to a changed parameter
        #=======================================================================
        root_node = NodegraphAPI.GetRootNode()
        ## NEW
        try:
            if args[2][2]:
                if args[2][2]['node'] == root_node and args[2][2]['param'].getParent().getName() == 'shot':
                    changeShot(args)
                elif args[2][2]['node'] == root_node and args[2][2]['param'].getParent().getName() == 'sequence':
                    updateSequence(args,args[2][2]['param'])
        except:
            pass
        
        
        #=======================================================================
        # publish_dir updated
        # check to see if it should create new directories
        #=======================================================================
        ## MUTATED
        try:
            if args[0][2]:
                if args[0][2]['node'] == self.node and args[0][2]['param'].getName() == 'publish_dir':
                    if args[0][2]['param'].getName() == 'publish_dir':
                        changeDirectory(args)
                elif args[0][2]['node'] == root_node and args[0][2]['param'].getParent().getName() == 'shot':
                    pass
                elif args[0][2]['node'] == root_node and args[0][2]['param'].getParent().getName() == 'sequence':
                    updateSequence(args,args[0][2]['param'])
        except:
            pass
 
    def createGafferThreeStack(self):
        #=======================================================================
        # creates a VBox for the gaffer three stack to displayed as the current gaffers for the user
        #=======================================================================
        widget = QtGui.QWidget()
        vbox = QtGui.QVBoxLayout()
        widget.setLayout(vbox)
        self.gaffer_splitter = QtGui.QSplitter()
        self.gaffer_tree_widget = GafferThreeStack(self,self.node)
        self.shot_browser = ShotBrowser(self,sequence=self.sequence)
        self.gaffer_splitter.addWidget(self.shot_browser)
        self.gaffer_splitter.addWidget(self.gaffer_tree_widget)
        vbox.addWidget(self.gaffer_splitter)
        return widget
    
    def updateShotGaffer(self,args=None):
        #=======================================================================
        # when the shot param is updated, repopulate the list of gaffers for the user to the corresponding shot
        # potentially need to change a few things... such as when it looks for the update...
        #=======================================================================
        def removeItems():
            for index in reversed(range(self.gaffer_tree_widget.topLevelItemCount())):
                self.gaffer_tree_widget.takeTopLevelItem(index)
        def addItems():
            item = self.getWorkingItem()
            #root_node = item.getPublishNode()
            root_node = item.getKeyNode()
            for child in root_node.getParameter('nodeReference').getChildren(): #group_node
                node = NodegraphAPI.GetNode(child.getValue(0))
                version = node.getParameter('version').getValue(0)
                unique_hash = node.getParameter('hash').getValue(0)

                check_state = node._LiveGroupMixin__isEditable
                #print node , child
                item = GafferTreeNodeItem(self.gaffer_tree_widget,node,version=version,unique_hash=unique_hash,check_state=check_state)

        removeItems()
        addItems()
    
    def loadLiveGroup(self,display_type,column,version=None):
        #load the live group...
        #=======================================================================
        # column 1 == key
        # column 2 == shot
        # column 3 == block
        #=======================================================================
        #set version on the button...
        ## some where in here... its making the key_node load the shot_node reference... wtf?
        if not version:
            version = str(self.version_combobox.currentText())
        item = self.getWorkingItem()
        if column == 1:
            dir = 'key'
            group_node = item.getKeyNode()
        elif column == 2:
            dir = 'live_group'
            group_node = item.getShotNode()

        if display_type != 'gaffer':
            live_group = NodegraphAPI.ConvertGroupToLiveGroup(group_node)
            publish_dir = '%s/%s/%s/gaffer.livegroup'%(self.getPublishDir(),dir,version)
            live_group.getParameter('source').setValue(publish_dir,0)
            live_group.load()
            new_root_node = live_group.convertToGroup()
            item = self.getWorkingItem()
            if column ==1:
                item.setKeyNode(new_root_node)
            elif column ==2:
                publish_dir = self.getPublishDir()  + '/live_group'
                
            self.updateShotGaffer()
            for index in reversed(range(self.shot_browser.topLevelItemCount())):
                self.shot_browser.takeTopLevelItem(index)
            self.shot_browser.populate() 
            
        elif display_type == 'gaffer':
            item = self.gaffer_tree_widget.currentItem()
            publish_dir = item.getPublishDir()
            version = str(version)
    
            gaffer_loc = '%s/%s/gaffer.livegroup'%(publish_dir,version)
            live_group = item.getNode()
            live_group.getParameter('source').setValue(gaffer_loc,0)
            item.setText(1,version)
        
            #item = self.gaffer_tree_widget.currentItem()
            #item.setNode(new_root_node)
            #item.setText(1,version)
            #print item.text(0)
            #print item.getRootNode()
            
            #new_key_node = NodegraphAPI.GetNode(new_root_node.getParameter('nodeReference.key_node').getValue(0))
            #item.setKeyNode(new_key_node)
            #item.setShotNode(new_root_node)
   
        
        self.display_versions_widget.close()
    
    def displayVersions(self,display_type=None,column=1):
        #=======================================================================
        # creates a new widget for the user to view the versions currently available
        # the user can change the version and check the release notes on each version 
        # before accepting this version
        #=======================================================================
        #publish_dir = 'C:/Users/Foundry/Documents/WinAsset/dev/gafferThree/publish/pipeline/999/shots/999_030/1502326737'
        self.display_versions_widget = QtGui.QWidget()
        
        
        vbox = QtGui.QVBoxLayout()
        notes_label = QtGui.QLabel()
        do_stuff = QtGui.QPushButton('load version...')
        if display_type != 'gaffer':
            item = self.getWorkingItem()
            if column ==1:
                publish_dir = self.getPublishDir()  + '/key'
            elif column ==2:
                publish_dir = self.getPublishDir()  + '/live_group'
        elif display_type == 'gaffer':
            item = self.gaffer_tree_widget.currentItem()
            publish_dir = item.getPublishDir()
        
        version = item.text(column)
        do_stuff.clicked.connect(lambda value: self.loadLiveGroup(display_type,column))
        self.version_combobox = Versions(publish_dir=publish_dir,label=notes_label,version=version)

        vbox.addWidget(self.version_combobox)
        vbox.addWidget(notes_label) 
        vbox.addWidget(do_stuff)
        self.display_versions_widget.setLayout(vbox)
        self.display_versions_widget.show()

    
    #===========================================================================
    # HELPER FUNCTIONS
    #===========================================================================
    def getItemList(self,item):
        #===================================================================
        # returns all children underneath a specific item
        #===================================================================
        if item.childCount() > 0:
            for index in range(item.childCount()):
                child = item.child(index)
                #print 'append %s'%child.getHash()
                self.item_list.append(child)
                if child.childCount() > 0:
                    self.getItemList(child)
        return self.item_list
    
    def createValueParam(self,name):
        factory = UI4.FormMaster.KatanaFactory.ParameterWidgetFactory
        locationPolicy = UI4.FormMaster.CreateParameterPolicy(None, self.node.getParameter(name))
        w = factory.buildWidget(self, locationPolicy)          
        return w         

    def connectInsideGroup(self,node_list,parent_node):
        send_port =parent_node.getSendPort('in')
        return_port = parent_node.getReturnPort('out')
        if len(node_list) == 0:
            send_port.connect(return_port)
        elif len(node_list) == 1:
            node_list[0].getOutputPortByIndex(0).connect(return_port)
            node_list[0].getInputPortByIndex(0).connect(send_port)
            
        elif len(node_list) == 2:
            node_list[0].getInputPortByIndex(0).connect(send_port)    
            node_list[1].getOutputPortByIndex(0).connect(return_port)

            node_list[0].getOutputPortByIndex(0).connect(node_list[1].getInputPortByIndex(0))
            
            NodegraphAPI.SetNodePosition(node_list[0],(0,100))
        elif len(node_list) > 2:
            for index, node in enumerate(node_list[:-1]):
                node.getOutputPortByIndex(0).connect(node_list[index+1].getInputPortByIndex(0))
                NodegraphAPI.SetNodePosition(node,(0,index * -100))
            node_list[0].getInputPortByIndex(0).connect(send_port)    
            node_list[-1].getOutputPortByIndex(0).connect(return_port)
            NodegraphAPI.SetNodePosition(node_list[-1],(0,len(node_list) * -100))           
    #===========================================================================
    # GETTERS / SETTERS
    #===========================================================================
    
    def getShotList(self):
        #=======================================================================
        # returns a list of shots based off of the graph state variable 'shots' during creation
        #=======================================================================
        return self.shot_list
    
    def setShotList(self):
        root = NodegraphAPI.GetRootNode()
        shot_list = []
        if root.getParameter('variables.shot'):
            shots = root.getParameter('variables.shot.options')
            for child in shots.getChildren():
                shot_list.append(child.getValue(0))
        self.shot_list = shot_list
        return shot_list
    
    def setShot(self,shot):
        self.shot = shot
        
    def getShot(self):
        return self.shot
    
    def setSequence(self,sequence):
        #=======================================================================
        # sets the sequence for the node param/treewidget/editor class
        #=======================================================================
        self.sequence = sequence
        self.node.getParameter('sequence').setValue(sequence,0)
        self.shot_browser.headerItem().setText(0,sequence)
        
    def getSequence(self):
        return self.sequence   
     
    def setWorkingItem(self,item):
        #=======================================================================
        # this attribute is the current selection in the ShotBrowser TreeWidget
        #=======================================================================
        self.workingItem = item
        
    def getWorkingItem(self):
        return self.workingItem
    
    def getPublishDir(self):
        #=======================================================================
        # returns the directory which holds the livegroups for the shot
        #=======================================================================
        main_widget = self
        
        item = main_widget.getWorkingItem()
        unique_hash = item.getHash()
        
        sequence = main_widget.node.getParameter('sequence').getValue(0)
        #print item.getItemType(), unique_hash
        
        if item.getItemType() == 'shot' or item.getItemType() == 'master':
            
            location = main_widget.node.getParameter('publish_dir').getValue(0) + '/%s/shots/%s'%(sequence,unique_hash)
        elif item.getItemType() == 'block':
            location = main_widget.node.getParameter('publish_dir').getValue(0) + '/%s/blocks/%s'%(sequence,unique_hash)

        return location
    
    def getShotGroup(self):
        #=======================================================================
        # returns the group container holding all of the gaffers for this shot
        # group --> group (shot/sequence) --> GS --> VEG --> !!!GROUP!!! --> GS --> LG --> Gaffer
        #=======================================================================
        #shot = self.node.getParameter('shot').getValue(0)
        shot = self.getShot()
        veg_node = NodegraphAPI.GetNode(self.node.sequence_gs.getParameter('%s%s'%(settings.SHOT_PREFIX,shot)).getValue(0))
        live_group = veg_node.getChildByIndex(0)
        return live_group            
    
class DisplayNotesCreate(QtGui.QMainWindow):
    #===========================================================================
    # pop up window for publishing
    #===========================================================================
    def __init__(self,parent=None,name=None,publish_type=None,item=None):
        super (DisplayNotesCreate,self).__init__(parent)
        def setupGUI():
            widget = QtGui.QWidget()
            #self.size
            #self.resize(480,270)
            
            self.setMinimumSize(480,270)
            layout = QtGui.QGridLayout()
            self.publish_state = 0
    
            self.besterest_button = QtGui.QPushButton()
            self.besterest_button.clicked.connect(self.setPublishState)
            #self.besterest_button.setFlat(True)
            self.besterest_button.setStyleSheet("background-color: rgb(235, 150, 150);border: none;")
            
            self.label = QtGui.QLabel(name)
            self.text_edit = QtGui.QPlainTextEdit()
            self.ok = QtGui.QPushButton('ok')
            self.cancel = QtGui.QPushButton('cancel')
            self.ok.clicked.connect(self.okPressed)
            self.cancel.clicked.connect(self.cancelPressed)
            self.text_edit.setMinimumHeight(200)
            self.besterest_button.setMinimumHeight(200)
            self.besterest_button.setSizePolicy(QtGui.QSizePolicy.Expanding, QtGui.QSizePolicy.Expanding)
            

            layout.addWidget(self.besterest_button,1,0,1,2)
            layout.addWidget(self.label,0,0,1,8)
            layout.addWidget(self.text_edit,1,2,1,6)
            layout.addWidget(self.ok,2,0,1,4)
            layout.addWidget(self.cancel,2,4,1,4)
            
            widget.setLayout(layout)
            self.setCentralWidget(widget)
            
        self.main_widget = self.getMainWidget(self)
        self.name = name
        #self.publish_dir = publish_dir
        self.publish_type = publish_type
        
        setupGUI()
        #self.update()
    
    def setAsLive(self,publish_loc,node,text,item,version):
        #=======================================================================
        # sets up this publish to be live
        #=======================================================================
        if self.getPublishState() == 1:
            
            live_dir = publish_loc[:publish_loc.rindex('/')] + '/live'
            live_file = live_dir + '/gaffer.livegroup'
            if os.path.exists(live_file):
                os.remove(live_file)
            if os.path.exists(live_file):
                os.remove(live_dir +'/notes.csv')
                
                
            #===================================================================
            # convert and publish
            #===================================================================
            if node.getType() == 'Group':
                node = NodegraphAPI.ConvertGroupToLiveGroup(node)
            node.publishAssetAndFinishEditingContents(live_dir + '/gaffer.livegroup')
            if item.getItemType() != 'gaffer':
                new_shot_node = node.convertToGroup()
                item.setShotNode(new_shot_node)
            elif item.getItemType == 'gaffer':
                item.setNode(node)
            #os.symlink(publish_loc +'/gaffer.livegroup', live_file)
            #===================================================================
            # bypassing symlinking for now because itse a bug...
            # which is screwing me... because its already published... so I gotta republish it?
            # lol
            #===================================================================
            file = open(live_dir +'/notes.csv','w')
            file.write(version)
            file.close()
            
            file = open(publish_loc +'/live.csv','w')
            file.write('hiya!')
            file.close()
            
    def publishShotGroup(self,item=None):
        #=======================================================================
        # publishes the live group containing all of the shot gaffers
        #=======================================================================
        def getVersion(location):
            versions = os.listdir(location)
            versions.remove('live')
            if len(versions)==0:
                next_version = 'v000'
            else:
                versions = [int(version[1:]) for version in versions]
                next_version = 'v'+str(sorted(versions)[-1] + 1).zfill(3)
            
            return next_version
            
        def createNote(publish_loc,version):
            #===================================================================
            # Apparently these guys can inherit from the enclosing scope... good to know
            # thats how the item thingy got in here...
            #===================================================================
            #How to publish NOT the first key... so that it goes SHOT --> Down...
            def publishAllGroups(item,note):   
                #===============================================================
                # start of recursive function to run through each subgroup and publish them
                #===============================================================
                publish_loc,version = getPublishDir(item)
                if item.getItemType() in ['block','master']:
                    num_children = item.childCount()
                    for index in range (num_children):
                        child = item.child(index)
                        publishAllGroups(child,note)

                ### Below the recursion to inverse the winding order...
                self.main_widget.setWorkingItem(item)
                self.main_widget.setShot(str(item.text(0)))
                self.main_widget.updateShotGaffer()
                # Statement to check for original item, if it is, dont publish the key
                if item != orig_item:
                    self.publishGafferGroup(item, note)
                #Publish the group
                if item.getItemType() in ['block','master']:
                    publishGroup(publish_loc,item,version)
                        
            def publishGroup(publish_loc,item,version):
                #===============================================================
                # publishes the group and writes out the notes...
                #===============================================================
                os.mkdir(publish_loc)
                Utils.EventModule.ProcessAllEvents()
                group = item.getShotNode()
                live_group = NodegraphAPI.ConvertGroupToLiveGroup(group)
                if not live_group.getParameter('version'):
                    live_group.getParameters().createChildString('version',version)
                live_group.getParameter('version').setValue(version,0)
                live_group.publishAssetAndFinishEditingContents(publish_loc + '/gaffer.livegroup')
                new_shot_node = live_group.convertToGroup()
                #live_group.convertToGroup()

                #===============================================================
                # write notes to disk...
                #===============================================================
                file = open(publish_loc +'/notes.csv','w')
                file.write(text)
                file.close()
                
                self.setAsLive(publish_loc,new_shot_node,text,item,version)
                #===============================================================
                # reset references
                #===============================================================
                new_key_node = NodegraphAPI.GetNode(item.getRootNode().getParameter('nodeReference.key_node').getValue(0))
                item.setKeyNode(new_key_node)
                item.setShotNode(new_shot_node)
                item.setText(2,version)
                if item.getRootNode().getParameter('expanded'):
                    if item.isExpanded() == True:
                        item.getRootNode().getParameter('expanded').setValue('True',0)
                    elif item.isExpanded() == False:
                        item.getRootNode().getParameter('expanded').setValue('False',0)


            #text, ok = QtGui.QInputDialog.getText(self, 'Publish Note', name)
            ## somehow need to send the signal fro mDisplayNotesCreate to here...
            #DisplayNotesCreate
            text = self.text_edit.toPlainText()
            publishAllGroups(item,text)

            for index in reversed(range(self.main_widget.shot_browser.topLevelItemCount())):
                self.main_widget.shot_browser.takeTopLevelItem(index)
            self.main_widget.shot_browser.populate()    
 
        def getPublishDir(item):
            if not item:
                item = self.main_widget.getWorkingItem()
            unique_hash = item.getHash()
            
            sequence = self.main_widget.node.getParameter('sequence').getValue(0)
            if item.getItemType() == 'block':
                location = self.main_widget.node.getParameter('publish_dir').getValue(0) + '/%s/blocks/%s/live_group'%(sequence,unique_hash)
            elif item.getItemType() == 'master':
                location = self.main_widget.node.getParameter('publish_dir').getValue(0) + '/%s/shots/%s/live_group'%(sequence,unique_hash)
            elif item.getItemType() == 'shot':
                location = self.main_widget.node.getParameter('publish_dir').getValue(0) + '/%s/shots/%s/key'%(sequence,unique_hash)
            unique_hash = item.getHash()
            version = getVersion(location)
            publish_loc = '%s/%s'%(location,version)
            return publish_loc , version
        
        if not item:
            item = self.main_widget.getWorkingItem()
            
        if item.getItemType() == 'shot':
            return
        
        orig_item = item
        orig_hash = item.getHash()
        
        publish_loc,version = getPublishDir(item)
        #if not os.path.exists(publish_loc):
            #os.mkdir(publish_loc)
            
        createNote(publish_loc,version)  

    def publishGafferGroup(self,item=None,note=None):
        #=======================================================================
        # publishes the live group containing all of the shot gaffers - this will be the group called "key" in most cases
        # and only publishes the gaffers... not the hierarchy below... to publish an entire hierarchy use "publishBlock"
        #=======================================================================
        def getVersion(location):
            versions = os.listdir(location)
            versions.remove('live')
            versions = [int(version[1:]) for version in versions]
            if len(versions) == 0:
                next_version = 'v000'
            else:
                next_version = 'v'+str(sorted(versions)[-1] + 1).zfill(3)
            return next_version
            
            
        def createNote(publish_loc,version,item,note=None):
            #Sequence/Shot/Gaffer
            def publishAllShotGaffers(text,item):
                ### this function... is probably making it run through and publish the same gaffers?
                for index in range(self.main_widget.gaffer_tree_widget.topLevelItemCount()):
                    item = self.main_widget.gaffer_tree_widget.topLevelItem(index)
                    #self.main_widget.gaffer_tree_widget.saveGaffer(item,note=text)
                    self.publishGaffer(item,note=text)
            text = self.text_edit.toPlainText()

            #text, ok = QtGui.QInputDialog.getText(self, 'Publish Note', name)
            os.mkdir(publish_loc)
            publishAllShotGaffers(text,item)
            Utils.EventModule.ProcessAllEvents()
            group = item.getKeyNode()
            live_group = NodegraphAPI.ConvertGroupToLiveGroup(group)
            if not live_group.getParameter('version'):
                live_group.getParameters().createChildString('version',version)
            live_group.getParameter('version').setValue(version,0)
            live_group.publishAssetAndFinishEditingContents(publish_loc + '/gaffer.livegroup')
            new_key_node = live_group.convertToGroup()
            #self.main_widget.shot_version_button.setText(version)
            #===============================================================
            # write notes to disk...
            #===============================================================
            file = open(publish_loc +'/notes.csv','w')
            file.write(text)
            file.close()
            
            self.setAsLive(publish_loc,new_key_node,text,item,version)
                    
            #===================================================================
            # reset attributes/parameters
            #===================================================================
            item.setKeyNode(new_key_node)

            self.main_widget.updateShotGaffer()
            item.setText(1,version)
        
        if not item:
            item = self.main_widget.getWorkingItem()
            
        unique_hash = item.getHash()
        
        sequence = self.main_widget.node.getParameter('sequence').getValue(0)
        if item.getItemType() == 'shot':
            location = self.main_widget.node.getParameter('publish_dir').getValue(0) + '/%s/shots/%s/key'%(sequence,unique_hash)
        elif item.getItemType() == 'block':
            location = self.main_widget.node.getParameter('publish_dir').getValue(0) + '/%s/blocks/%s/key'%(sequence,unique_hash)
        
        elif item.getItemType() == 'master':
            location = self.main_widget.node.getParameter('publish_dir').getValue(0) + '/%s/shots/master/key'%(sequence)
        
        #print location
        version = getVersion(location)
        
        publish_loc = '%s/%s'%(location,version)
        createNote(publish_loc,version,item,note)
 
    def publishGaffer(self,item=None,note=None):
        #=======================================================================
        # publishes an individual gaffer inside of a group stack of gaffers
        #=======================================================================
        def getVersion(location):
            versions = os.listdir(location)
            if versions == ['live']:
                next_version = 'v000'
            else:
                versions.remove('live')
                versions = [int(version[1:]) for version in versions]
                next_version = 'v'+str(sorted(versions)[-1] + 1).zfill(3)
            return next_version
        
        def createNote(publish_loc,item,version,note):
            text = self.text_edit.toPlainText()

            os.mkdir(publish_loc)
            live_group.getParameter('version').setValue(version,0)
            live_group.publishAssetAndFinishEditingContents(publish_loc + '/gaffer.livegroup')
            
            #===============================================================
            # write notes to disk...
            #===============================================================
            file = open(publish_loc +'/notes.csv','w')
            file.write(text)
            file.close()
            
            self.setAsLive(publish_loc,live_group,text,item,version)
            
            item.setCheckState(0, QtCore.Qt.Unchecked)
            item.setText(1,version)

        if not item:
            item = self.main_widget.gaffer_tree_widget.currentItem()
        publish_dir = item.getPublishDir()
        live_group = item.getNode()
        version = getVersion(publish_dir)
        publish_loc = '%s/%s'%(publish_dir,version)
        #if not os.path.exists(publish_dir):
            #os.mkdir(publish_dir)
        createNote(publish_loc,item,version,note)
            
    def getMainWidget(self,widget):
        if isinstance(widget, GafferThreeSequenceEditor):
            return widget
        else:
            return self.getMainWidget(widget.parent())
        
    def okPressed(self):
        
        if self.publish_type == 'key':
            self.publishGafferGroup()
            
        elif self.publish_type == 'shot':
            self.publishShotGroup()
            
        elif self.publish_type == 'gaffer':
            self.publishGaffer()
            
        self.close()

    def cancelPressed(self):
        print 'cancel'
        self.close()
        
    def setPublishState(self):
        self.publish_state += 1
        #publish_state = self.publish_state %2
        if self.publish_state % 2 == 0:
            self.besterest_button.setStyleSheet("background-color: rgb(235, 150, 150);border: none;")
        elif self.publish_state % 2 == 1:
            self.besterest_button.setStyleSheet("background-color: rgb(150, 235, 150);border: none;")
        #print publish_state
        
    def getPublishState(self):
        return self.publish_state % 2

class GafferThreeStack(QtGui.QTreeWidget):
    #===========================================================================
    # class that acts as the layer stack for holding all of the GafferThrees
    # for this shot
    #===========================================================================
    def __init__(self,parent,node):
        super(GafferThreeStack,self).__init__(parent)

        self.node = node
        self.main_widget = self.parent()
        self.setMinimumWidth(100)
        #=======================================================================
        # Setup Header
        #=======================================================================
        self.head = self.header() # gets the QHeaderView
        self.head.setClickable(True)
        header_item = self.setHeaderLabels( ['Gaffer','Version'] )   
        self.setHeaderItem(header_item)
        self.setAlternatingRowColors(True)
        #self.head.setResizeMode(0,QtGui.QHeaderView.Stretch)
        self.head.setStretchLastSection(False)
        self.setColumnWidth(1,60)
        self.head.setResizeMode(1,QtGui.QHeaderView.Fixed)
        
        #=======================================================================
        # Signals
        #=======================================================================
        self.head.sectionClicked.connect(self.createGaffer)
        self.itemChanged.connect(self.itemCheckBoxSignal)

   
    def itemCheckBoxSignal(self,item):
        #=======================================================================
        # signal next to the gaffer in the qtree widget that allows the user to toggle on/off the live group edit mode
        #=======================================================================
        if item:
            node = item.getNode()
            node.setName(str(item.text(0)))     
            if item.checkState(0) == QtCore.Qt.Checked:
                #print 'selecting %s'%item.text(0)
                item.getNode()._setEditable(True, updateContentLock=True)
                pass
            else:

                pass
    
    def selectionChanged(self, event,*args, **kwargs):
        #=======================================================================
        # will update the teledrop parameters to display the currenet gaffer that the user has selected inside of the gaffer treewidget
        #=======================================================================
        item = self.currentItem()

        if item:
            index = self.currentIndex()
            if index.column() == 0:
                '''
                sets the node selected in the layer stack to have its parameters viewed
                '''
                node = self.currentItem().getNode().getChildByIndex(0)
                if self.main_widget.splitter.widget(1) and node:
                    self.main_widget.splitter.widget(1).setParent(None)
                
                    self.main_widget.splitter.addWidget(self.main_widget.scroll)
                    self.main_widget.params_policy.setValue(node.getName(),0)


        return QtGui.QTreeWidget.selectionChanged(self, event, *args, **kwargs)
                                      
    def getMainWidget(self,widget):
        if isinstance(widget, GafferThreeSequenceEditor):
            return widget
        else:
            return self.getMainWidget(widget.parent())
    
    def createNodeReference(self,node,node_ref,param_name,param=None):
        if not param:
            param = node.getParameters()
        new_param = param.createChildString(param_name,'')
        new_param.setExpressionFlag(True)
        new_param.setExpression('@%s'%node_ref.getName())
        return new_param
    
    def createGaffer(self,event):
        def getGroupStack():
            item = self.getMainWidget(self).getWorkingItem()
            return item.getKeyNode()
                   
        def createLiveGroup(root_node):
            
            if len(root_node.getChildren()) == 0:
                previous_port = root_node.getSendPort('in')
            else:
                previous_port = root_node.getChildByIndex(len(root_node.getChildren())-1).getOutputPortByIndex(0)
            live_group = NodegraphAPI.CreateNode('LiveGroup',root_node)

            live_group._setEditable(True, updateContentLock=True)
            gaffer_three = NodegraphAPI.CreateNode('GafferThree',live_group)
            live_group.addInputPort('in')
            live_group.addOutputPort('out')
            
            live_group.getSendPort('in').connect(gaffer_three.getInputPortByIndex(0))
            gaffer_three.getOutputPortByIndex(0).connect(live_group.getReturnPort('out'))
            live_group.getInputPortByIndex(0).connect(previous_port)
            live_group.getOutputPortByIndex(0).connect(root_node.getReturnPort('out'))    
            return live_group , gaffer_three    
        if event == 0:
            # shots --> group_stack --> veg --> lg --> gs --> lg --> gaffer three

            group_stack = getGroupStack()
            
            live_group,gaffer_three = createLiveGroup(group_stack)
            
            item = GafferTreeNodeItem(self,live_group)
            live_group.getParameters().createChildString('version','')
            live_group.getParameters().createChildString('hash',str(item.getHash()))
            param = group_stack.getParameter('nodeReference')
            #print group_stack,live_group,live_group.getName(),param
            self.createNodeReference(group_stack,live_group,live_group.getName(),param=param)
            
    def contextMenuEvent(self, event): 
        ''' 
        popup menu created when the rmb is hit - has a submethod 'actionPicker' which is choosing another method
        inside of this class to do an action when that particular name is chosen
        
        '''
        def actionPicker(action):   
            if action.text() == 'Go To Node':
                self.goToNode(action)
            elif action.text() == 'Save Gaffer':
                #print self.main_widget
                
                item = self.currentItem()
                self.publishGaffer(item)
            elif action.text() == 'Get Publish Dir':
                print self.currentItem().getPublishDir()
        pos = event.globalPos()
        menu = QtGui.QMenu(self)
        menu.addAction('Go To Node')
        menu.addAction('Get Publish Dir')
        menu.addSeparator()
        menu.addAction('Save Gaffer')
        menu.popup(pos)   
        action = menu.exec_(QtGui.QCursor.pos())
        if action is not None:
            actionPicker(action)    
    
    def publishGaffer(self,item,note=None,name=None):
        #=======================================================================
        # publishes an individual gaffer inside of a group stack of gaffers
        #=======================================================================
        def getVersion(location):
            versions = os.listdir(location)
            if versions == ['live']:
                next_version = 'v000'
            else:
                versions.remove('live')
                versions = [int(version[1:]) for version in versions]
                next_version = 'v'+str(sorted(versions)[-1] + 1).zfill(3)
            return next_version
        shot = self.main_widget.workingItem.text(0)
        sequence = self.main_widget.node.getParameter('sequence').getValue(0)
        location = self.currentItem().getPublishDir()
        version = getVersion(location)
        gaffer_name = item.text(0)
        name = '%s|%s|%s|%s'%(sequence,shot,gaffer_name,version)

        notes_window = DisplayNotesCreate(parent=self,name=name,publish_type='gaffer')
        notes_window.show()

        #createNote(publish_loc,item,version,note)
    
    def disableItem(self,item):
        font = item.font(0)
        node = self.currentItem().getNode()
        
        if node.isBypassed() == False:
            font.setStrikeOut(True)
            node.setBypassed(True)
        elif node.isBypassed() == True:
            font.setStrikeOut(False)
            node.setBypassed(False)
        item.setFont(0,font)
    
    def deleteItem(self,item):
        node = item.getNode()
        main_widget = self.getMainWidget(self)
        key_node = main_widget.getWorkingItem().getKeyNode()
        for param in key_node.getParameter('nodeReference').getChildren():
            if param.getValue(0) == node.getName():
                key_node.getParameter('nodeReference').deleteChild(param)
                
                
        send_port = node.getInputPortByIndex(0).getConnectedPorts()[0]
        return_port = node.getOutputPortByIndex(0).getConnectedPorts()[0]
        send_port.connect(return_port)
        node.delete()
        
        parent_item = self.invisibleRootItem()
        index = parent_item.indexOfChild(item)
        parent_item.takeChild(index)

    def goToNode(self,action):
        
        #=======================================================================
        # Changes the nodegraph to the selected items node, if it is not a group node, then it goes to its parent
        # as the parent must be a group... (hopefully)
        #=======================================================================
        
        item = self.currentItem()

        node = item.getNode()
        nodeGraphTab = UI4.App.Tabs.FindTopTab('Node Graph')
        nodeGraphTab._NodegraphPanel__navigationToolbarCallback(node.getName(),'useless')
    
    #===========================================================================
    # the popup display for the versioning system for display/load of different version
    #===========================================================================

    def getPublishDir(self):
        #=======================================================================
        # returns the directory which holds the livegroups for the shot
        #=======================================================================
        main_widget = self.getMainWidget(self)
        
        item = main_widget.getWorkingItem()
        unique_hash = item.getHash()
        
        sequence = main_widget.node.getParameter('sequence').getValue(0)
        if item.getItemType() == 'shot' or item.getItemType() == 'master':
            location = main_widget.node.getParameter('publish_dir').getValue(0) + '/%s/shots/%s/versions'%(sequence,unique_hash)
        elif item.getItemType() == 'block':
            location = main_widget.node.getParameter('publish_dir').getValue(0) + '/%s/blocks/%s/versions'%(sequence,unique_hash)

        return location

    
    #===========================================================================
    # override event handlers
    #===========================================================================
    
    def mouseDoubleClickEvent(self, event,*args, **kwargs):
        item = self.currentItem()
        index = self.currentIndex()

        item.setFlags(item.flags() | QtCore.Qt.ItemIsEditable)
        if item:
            if index.column()!=0:
                item.setFlags(item.flags() & ~QtCore.Qt.ItemIsEditable)
        QtGui.QTreeWidget.mouseDoubleClickEvent(self, event,*args, **kwargs)
    
    def keyPressEvent(self,event, *args, **kwargs):
        #print event.key()
        if event.key() == 68:
            #print 'd pressed'
            current_items = self.selectedItems()
            for item in current_items:
                self.disableItem(item)


        elif event.key() in [16777219, 16777223]:
            # Del Pressed
            current_items = self.selectedItems()
            for item in current_items:
                self.deleteItem(item)
    
    def mouseReleaseEvent(self, event,*args, **kwargs):
        item = self.itemAt( event.pos() )
        if item:
            index = self.currentIndex()
            if index.column() == 0:
                pass
                #print index
            elif index.column() == 1:
                ## load up version dir...
                if event.button() == 1:
                    main_widget = self.getMainWidget(self)
                    #version = main_widget.getWorkingItem().text(index.column())
                    main_widget.displayVersions(display_type='gaffer',column=index.column())
                    
                    #self.displayVersions(display_type='gaffer')
                    #print index
    
            return QtGui.QTreeWidget.mouseReleaseEvent(self, event,*args, **kwargs)

class GafferTreeNodeItem( QtGui.QTreeWidgetItem ):
    def __init__( self, parent ,node,version='',unique_hash=None,check_state=2):
        super( GafferTreeNodeItem, self ).__init__( parent )
        self.node = node
        self.node.getChildByIndex(0).setShowIncomingScene(True)

        self.setText(0,node.getName())
        self.setText(1,version)

        self.setFlags(self.flags() | QtCore.Qt.ItemIsUserCheckable)
        if check_state == False:
            check_state = 0
        elif check_state == True:
            check_state = 2
            
        self.setCheckState(0, check_state) 

        self.hash = self.createPublishDir(unique_hash=unique_hash)
    def createPublishDir(self,unique_hash=None):
        #=======================================================================
        # generates a unique hash for the gaffer live group and then creates the 
        # directories on disk for them to be save into 
        #=======================================================================
        def checkHash(thash,location):
            thash = int(math.fabs(hash(str(thash))))
            
            if str(thash) in os.listdir(location):
                thash = int(math.fabs(hash(str(thash))))
                return checkHash(str(thash),location)
            #print thash
            return thash
        root_node = self.treeWidget().node
        main_widget = self.getMainWidget(self.treeWidget())
        #current_item = main_widget.shot_browser.currentItem()
        shot = main_widget.getShot()
        sequence = main_widget.getSequence()
        working_item = main_widget.getWorkingItem()
        working_item_hash = working_item.getHash()
        if working_item.getItemType() == 'shot':
            location = root_node.getParameter('publish_dir').getValue(0) + '/%s/shots/%s_%s/gaffers'%(sequence,sequence,shot)
        elif working_item.getItemType() == 'block':
            location = location = root_node.getParameter('publish_dir').getValue(0) + '/%s/blocks/%s/gaffers'%(sequence,working_item_hash)
        elif working_item.getItemType() == 'master':
            location = root_node.getParameter('publish_dir').getValue(0) + '/%s/shots/%s/gaffers'%(sequence,shot)
        if unique_hash:
            self.hash = unique_hash
        else:
            self.hash = hash(self.node.getName())
            self.hash = checkHash(self.hash,location)
        if not os.path.exists('%s/%s'%(location,self.hash)):
            os.mkdir('%s/%s'%(location,self.hash))
            os.mkdir('%s/%s/live'%(location,self.hash))
        
        self.publish_dir = '%s/%s'%(location,self.hash)
        return self.hash
    def getMainWidget(self,widget):
        if isinstance(widget, GafferThreeSequenceEditor):
            return widget
        else:
            return self.getMainWidget(widget.parent())
    def setNode(self,node):
        self.node = node
    def getNode(self):
        return self.node
    
    def setHash(self,unique_hash):
        self.hash = unique_hash
    def getHash(self):
        return self.hash
    def setPublishDir(self,publish_dir):
        self.publish_dir = publish_dir
    def getPublishDir(self):
        return self.publish_dir
    def getItemType(self):
        return 'gaffer'

class Versions(QtGui.QComboBox):
    '''
    a way to create new nodes inside of the widget itself
    '''
    def __init__(self,parent=None,publish_dir='',label=QtGui.QLabel(),version='live'):
        super(Versions,self).__init__(parent)
        self.main_widget = self.parent()
        
        self.setLineEdit(QtGui.QLineEdit("Select & Focus", self))
        self.publish_dir = publish_dir
        self.version_list = os.listdir(publish_dir)
        self.label = label
        
        self.setEditable(True)
        self.currentIndexChanged.connect(self.indexChanged)
        self.completer = QtGui.QCompleter( self )
        self.completer.setCompletionMode( QtGui.QCompleter.PopupCompletion )
        self.completer.setCaseSensitivity( QtCore.Qt.CaseInsensitive )
        self.completer.setPopup( self.view() )
        self.setCompleter( self.completer )

        self.pFilterModel = QtGui.QSortFilterProxyModel( self )

        self.populate()
        
        self.lineEdit().setText(version)
        self.update()
        self.setNote()
        
    def setNote(self):
        notes_dir = '%s/%s/notes.csv'%(self.publish_dir , self.currentText())
        if os.path.exists(notes_dir):
            with open(notes_dir, 'rb') as csvfile:
                note = csvfile.readlines()
                note_text = ''.join(note)
                self.label.setText(str(note_text))
                self.label.setWordWrap(True)
        else:
            self.label.setText('try making some notes...')
            self.label.setWordWrap(True)
            
    def indexChanged(self,event):
        self.setNote()
        

    def populate(self):
        #=======================================================================
        # adds all of the items to the model widget
        # adds color to the items       
        #=======================================================================
        createNewNodeWidget = self
        model = QtGui.QStandardItemModel()
        live_item = None
        for i, version in enumerate( self.version_list ):
            
            item = QtGui.QStandardItem(version)
            #===================================================================
            # set colors up
            #===================================================================
            if os.path.exists('%s/%s/live.csv'%(self.publish_dir,version)):
                if live_item:
                    color = QtGui.QColor(94, 94, 60, 255)
                    brush = QtGui.QBrush(color)
                    live_item.setBackground(brush)
                color = QtGui.QColor(60, 94, 60, 255)
                brush = QtGui.QBrush(color)
                item.setBackground(brush)
                live_item = item
            #model.remove
            model.setItem(i, 0, item)

        createNewNodeWidget.setModel(model)
        createNewNodeWidget.setModelColumn(0)     
        
    def setModel( self, model ):
        super(Versions, self).setModel( model )
        self.pFilterModel.setSourceModel( model )
        self.completer.setModel(self.pFilterModel)

    def setModelColumn( self, column ):
        self.completer.setCompletionColumn( column )
        self.pFilterModel.setFilterKeyColumn( column )
        super(Versions, self).setModelColumn( column )      
              
    def view( self ):
        return self.completer.popup()  
              
    def next_completion(self):
        row = self.completer.currentRow()
        if not self.completer.setCurrentRow(row + 1):
            self.completer.setCurrentRow(0)
        index = self.completer.currentIndex()
        self.completer.popup().setCurrentIndex(index)
        #self.completer.popup().show()
        
    def previous_completion(self):
        row = self.completer.currentRow()
        numRows = self.completer.completionCount()
        if not self.completer.setCurrentRow(row - 1):
            self.completer.setCurrentRow(numRows-1)
        index = self.completer.currentIndex()
        self.completer.popup().setCurrentIndex(index)

    def event(self, event,*args, **kwargs):
        if (event.type()==QtCore.QEvent.KeyPress) and (event.key()==QtCore.Qt.Key_Tab):
            ## Shift Pressed
            self.next_completion()
            return True

        elif (event.type()==QtCore.QEvent.KeyPress) and (event.key()==16777218):
            ## Shift Tab Pressed
            self.previous_completion()
            return True
        elif (event.type()==QtCore.QEvent.KeyPress) and (event.key() == 16777220 or event.key() == 16777221):
            print 'enter!'
            ## Enter Pressed

        
        return QtGui.QComboBox.event(self, event,*args, **kwargs)
    
class ShotBrowser(QtGui.QTreeWidget):
    #===========================================================================
    # Three types... 
    #     Master  - lighting rig for the entire sequence...
    #     Block   - container holding multiple shots
    #     Shot    - a single shot ShotBrowserItem(self,name='master',item_type='master')
    #===========================================================================
    def __init__( self, parent=None,sequence=''):
        super(ShotBrowser,self).__init__(parent=parent)
        self.head = self.header()
        self.head.setClickable(True)
        self.head.sectionClicked.connect(self.createShotGroup)
        sequence = QtGui.QTreeWidgetItem([sequence,'key','shot','block'])
        #self.head.setResizeMode(0,QtGui.QHeaderView.Stretch)
        self.setHeaderItem(sequence)
        self.head.setStretchLastSection(False)
        for x in range (1,4):
            self.setColumnWidth(x,60)
            self.head.setResizeMode(x,QtGui.QHeaderView.Fixed)
            
        self.setDragEnabled(True)
        self.setDropIndicatorShown(True)
        self.setDragDropMode(QtGui.QAbstractItemView.InternalMove)
        self.populate()
        self.itemChanged.connect(self.nodeNameChanged)
        self.item_list = []
        self.main_widget = self.getMainWidget(self)
        
    def contextMenuEvent(self, event): 
        ''' 
        popup menu created when the rmb is hit - has a submethod 'actionPicker' which is choosing another method
        inside of this class to do an action when that particular name is chosen
        '''
        def actionPicker(action):   
            if action.text() == 'Go To Node':
                self.goToNode(action)
            elif action.text() == 'Get Publish Dir':
                print self.main_widget.getWorkingItem().getPublishDir()
            elif 'Publish' in action.text():
                
                #===============================================================
                # get attributes to create the information to display to the user
                #===============================================================
                item = self.main_widget.getWorkingItem()
                unique_hash = item.getHash()
                
                sequence = self.main_widget.node.getParameter('sequence').getValue(0)
                if item.getItemType() == 'shot':
                    location = self.main_widget.node.getParameter('publish_dir').getValue(0) + '/%s/shots/%s/key'%(sequence,unique_hash)
                elif item.getItemType() == 'block':
                    location = self.main_widget.node.getParameter('publish_dir').getValue(0) + '/%s/blocks/%s/key'%(sequence,unique_hash)
                
                elif item.getItemType() == 'master':
                    location = self.main_widget.node.getParameter('publish_dir').getValue(0) + '/%s/shots/master/key'%(sequence)

                shot = self.main_widget.workingItem.text(0)
                sequence = self.main_widget.node.getParameter('sequence').getValue(0)
                version = self.getVersion(location)
                name = '%s|%s|%s'%(sequence,shot,version)
                
                #===============================================================
                # determine which button was pressed..
                #===============================================================
                if action.text() == 'Publish Shot Group':
                    self.publishShotGroup(name=name)
                elif action.text() == 'Publish Gaffers':
                    self.publishGafferGroup(name=name)

                
        pos = event.globalPos()
        menu = QtGui.QMenu(self)
        item = self.currentItem()
        menu.addAction('Go To Node')
        menu.addAction('Get Publish Dir')
        menu.addSeparator()
        menu.addAction('Publish Gaffers')
        if item.getItemType() in [ 'block' , 'master']:
            menu.addAction('Publish Shot Group')
        
        menu.popup(pos)   
        action = menu.exec_(QtGui.QCursor.pos())
        if action is not None:
            actionPicker(action)   
        
    def getVersion(self,location):
        versions = os.listdir(location)
        versions.remove('live')
        if len(versions)==0:
            next_version = 'v000'
        else:
            versions = [int(version[1:]) for version in versions]
            next_version = 'v'+str(sorted(versions)[-1] + 1).zfill(3)
        
        return next_version 
    
    def publishShotGroup(self,item=None,name=None):
        notes_window = DisplayNotesCreate(parent=self,name=name,publish_type='shot')
        notes_window.show()

    def publishGafferGroup(self,item=None,note=None,name=None):
        notes_window = DisplayNotesCreate(parent=self,name=name,publish_type='key')
        notes_window.show()
        
    def goToNode(self,action):
        #=======================================================================
        # Changes the nodegraph to the selected items node, if it is not a group node, then it goes to its parent
        # as the parent must be a group... (hopefully)
        #=======================================================================
        item = self.currentItem()
        node = item.getRootNode()
        nodeGraphTab = UI4.App.Tabs.FindTopTab('Node Graph')
        nodeGraphTab._NodegraphPanel__navigationToolbarCallback(node.getName(),'useless')
    
    def populate(self):
        def populateBlock(block_node,root_item,child):
            #===================================================================
            # recursive statement to search through all nodes and create the items for those nodes
            #===================================================================
            node = NodegraphAPI.GetNode(child.getValue(0))
            if node.getType() == 'VariableEnabledGroup':
                version = node.getChildByIndex(0).getParameter('version').getValue(0)
                unique_hash = node.getChildByIndex(0).getParameter('hash').getValue(0)
                shot = node.getParameter('pattern').getValue(0)
                item = ShotBrowserItem(root_item,root_node=node, shot_node = node, \
                                       key_node=node.getChildByIndex(0),key_version=version,\
                                       unique_hash=unique_hash,name=shot,item_type='shot')
            else:
                version = node.getParameter('version').getValue(0)
                unique_hash = node.getParameter('hash').getValue(0)
                block_node = node
                print block_node
                if block_node.getParameter('expanded'):
                    if block_node.getParameter('expanded').getValue(0) == 'True':
                        expanded = True
                    else:
                        expanded = False
                key_node = NodegraphAPI.GetNode(block_node.getParameter('nodeReference.key_node').getValue(0))
                shot_node = NodegraphAPI.GetNode(block_node.getParameter('nodeReference.shot_group').getValue(0))
                key_version = key_node.getParameter('version').getValue(0)
                shot_version = shot_node.getParameter('version').getValue(0)
                block_item = ShotBrowserItem(root_item,root_node=block_node,shot_node = shot_node, key_node=key_node,\
                                             key_version=key_version,shot_version=shot_version,block_version='',\
                                             unique_hash=unique_hash,name=block_node.getName(),item_type='block',expanded=expanded)
                for child in shot_node.getParameter('nodeReference').getChildren():
                    populateBlock(block_node,block_item,child)
        main_widget = self.getMainWidget(self)
        
        #=======================================================================
        # create directory for master light rig
        #=======================================================================
        sequence = main_widget.node.getParameter('sequence').getValue(0)
        publish_dir = main_widget.node.getParameter('publish_dir').getValue(0) + '/%s/shots/master'%(sequence)
        if not os.path.exists(publish_dir):
            dir_list = ['gaffers','key','live_group','publish']
            os.mkdir(publish_dir)
            for dir_item in dir_list:
                os.mkdir(publish_dir + '/%s'%dir_item)
                os.mkdir(publish_dir + '/%s/live'%dir_item)
        #=======================================================================
        # set up master item
        # this item is the same as a 'block' but with the special type of 'master'
        #=======================================================================
        sequence_root_node = NodegraphAPI.GetNode(main_widget.node.getParameter('sequence_node').getValue(0))
        sequence_master_group = NodegraphAPI.GetNode(sequence_root_node.getParameter('nodeReference.key_node').getValue(0))
        shot_root_node = NodegraphAPI.GetNode(sequence_root_node.getParameter('nodeReference.shot_group').getValue(0))
        key_version = sequence_master_group.getParameter('version').getValue(0)
        shot_version = shot_root_node.getParameter('version').getValue(0)
        master = ShotBrowserItem(self,root_node=sequence_root_node , shot_node=shot_root_node, \
                                 key_node=sequence_master_group, unique_hash='master', \
                                 shot_version = shot_version , key_version=key_version , \
                                 name='master',item_type='master',expanded=True)
        sequence_master_group.getOutputPortByIndex(0).connect(shot_root_node.getInputPortByIndex(0))
        shot_root_node.getOutputPortByIndex(0).connect(sequence_root_node.getReturnPort('out'))

        #=======================================================================
        # recursively populate the items under the shots group
        #=======================================================================
        for child in shot_root_node.getParameter('nodeReference').getChildren():
            populateBlock(shot_root_node,master,child)
            
    def nodeNameChanged(self,item):
        #=======================================================================
        # signal next to the gaffer in the qtree widget that allows the user to toggle on/off the live group edit mode
        #=======================================================================
        try:
            if item.getKeyNode():
                node = item.getKeyNode()
                node.getParent().setName(str(item.text(0)))     
        except:
            pass 

    def getMainWidget(self,widget):
        if isinstance(widget, GafferThreeSequenceEditor):
            return widget
        else:
            return self.getMainWidget(widget.parent())
    
    def createShotGroup(self):
        #=======================================================================
        # creates a new item container
        #=======================================================================
        ## create new publish directory
        main_widget = self.getMainWidget(self)
        current_item = self.currentItem()
        if current_item:
            if current_item.getItemType() == 'shot':
                parent_item = current_item.parent()
                if current_item.parent():
                    root_node = NodegraphAPI.GetNode(current_item.parent().getRootNode().getParameter('nodeReference.shot_group').getValue(0))
                else:
                    root_node = NodegraphAPI.GetNode(main_widget.node.getParameter('shot_node').getValue(0))
            elif current_item.getItemType() in ['master', 'block']:
                root_node = NodegraphAPI.GetNode(current_item.getRootNode().getParameter('nodeReference.shot_group').getValue(0))
                parent_item = current_item
        #else:
            #
        # Get ports
        if len(root_node.getChildren()) == 0:
            previous_port = root_node.getSendPort('in')
        else:
            previous_port = root_node.getChildByIndex(len(root_node.getChildren())-1).getOutputPortByIndex(0)
        
        #Create Nodes
        block_node = main_widget.node.createBlockGroup(root_node,name='New_Block')
        if not parent_item:
            #parent_item = self.topLevelItem(0)
            last_node = self.topLevelItem(0).getRootNode()
        else:
            last_node = parent_item.child(parent_item.childCount()-1).getRootNode()

        #Connect Nodes
        previous_port.connect(block_node.getInputPortByIndex(0))
        block_node.getOutputPortByIndex(0).connect(root_node.getReturnPort('out'))
        #Position Nodes
        current_pos = NodegraphAPI.GetNodePosition(last_node)
        new_pos = (current_pos[0],current_pos[1]-100)
        NodegraphAPI.SetNodePosition(block_node, new_pos)
        #Get Nodes
        shot_node = NodegraphAPI.GetNode(block_node.getParameter('nodeReference.shot_group').getValue(0))
        key_node = NodegraphAPI.GetNode(block_node.getParameter('nodeReference.key_node').getValue(0))
        #Create Item
        block_item = ShotBrowserItem(parent_item,shot_node=shot_node, root_node=block_node,key_node=key_node,\
                                     name=block_node.getName(),item_type='block')
        # Create Parameters
        version = block_node.getParameter('version').setValue(block_item.block_version,0)
        unique_hash = block_node.getParameter('hash').setValue(str(block_item.getHash()),0)
        return block_item

    def selectionChanged(self, *args, **kwargs):
        #=======================================================================
        # displays the gaffer stack for the currently selected shot block
        #=======================================================================
        main_widget = self.getMainWidget(self)
        if self.currentItem():
            main_widget.setShot(str(self.currentItem().text(0)))
            main_widget.setWorkingItem(self.currentItem())
            main_widget.updateShotGaffer()
            main_widget.gaffer_tree_widget.headerItem().setText(0,self.currentItem().text(0))
            #self.shot_browser.headerItem().setText(0,sequence)

        return QtGui.QTreeWidget.selectionChanged(self, *args, **kwargs)

    def dragMoveEvent(self, event,*args, **kwargs):
        #=======================================================================
        # handlers to determine if an item is droppable or not
        #=======================================================================
        self.item = self.currentItem()
        self.dragging = True
        self.current_parent = None
        current_item_over = self.itemAt(event.pos())
        root_flags = self.invisibleRootItem().flags()
        root_item = self.invisibleRootItem()
        
        if current_item_over:
            if current_item_over.getItemType() == 'block':
                self.current_parent = current_item_over
            elif current_item_over.getItemType() == 'shot':
                if current_item_over.parent(): 
                    self.current_parent = current_item_over.parent()
            elif current_item_over.getItemType() == 'master':
                self.current_parent = current_item_over
            else:
                self.current_parent = current_item_over

        else:
            root_item.setFlags(root_flags &  ~QtCore.Qt.ItemIsDropEnabled)
            self.current_parent = current_item_over
            return QtGui.QTreeWidget.dragMoveEvent(self, event,*args, **kwargs)
        return QtGui.QTreeWidget.dragMoveEvent(self, event,*args, **kwargs)
 
    def dropEvent(self, event, *args, **kwargs):
        #=======================================================================
        # on drop of the item, it will disconnect/reconnect it and reposition
        # all of the nodes inside...
        #=======================================================================
        def getAllRootNodes(item,vs_node_list=[]):
            if item:
                if item.getRootNode().getParameter('nodeReference.vs_node'):
                    #vs_node = NodegraphAPI.GetNode(item.getRootNode().getParameter('nodeReference.vs_node').getValue(0))
                    vs_node_list.append(item.getRootNode())
                return getAllRootNodes(item.parent(),vs_node_list)
            else:
                return vs_node_list      
        
        def disconnectItem(node,old_shot_node):
            #===================================================================
            # this will remove all referencing/linking to its existing parent
            #===================================================================
            # connect nodes
            #print '1714'
            #print node
            #print node.getInputPortByIndex(0).getConnectedPorts()
            print '---------- disconnect node ----------'
            print node
            if len(node.getInputPortByIndex(0).getConnectedPorts()) > 0:
                previous_port = node.getInputPortByIndex(0).getConnectedPorts()[0]
            if len(node.getOutputPortByIndex(0).getConnectedPorts()) > 0:
                next_port = node.getOutputPortByIndex(0).getConnectedPorts()[0]
    
            for output_port in node.getOutputPorts():
                input_ports = output_port.getConnectedPorts()
                for port in input_ports:
                    port.disconnect(output_port)
            
            for input_port in node.getInputPorts():
                output_ports = input_port.getConnectedPorts()
                for port in output_ports:
                    port.disconnect(input_port)
                    
            next_port.connect(previous_port)
            #update params
            for param in old_shot_node.getParameter('nodeReference').getChildren():
                #print param.getValue(0) , node.getName()
                if param.getValue(0) == node.getName():
                    old_shot_node.getParameter('nodeReference').deleteChild(param)
            
            # update variable switch if a shot has been moved...

            if self.item.getItemType() == 'shot':
                item = self.item
                shot = item.text(0)
                shot_string = '%s%s'%(settings.SHOT_PREFIX, shot)
                root_node_list = getAllRootNodes(item,vs_node_list=[])
                for root_node in root_node_list:
                    vs_node = NodegraphAPI.GetNode(root_node.getParameter('nodeReference.vs_node').getValue(0))
                    vs_node.removeInputPort(shot_string)
         
        def connectItem(parent_item,parent_node):
            #===================================================================
            # connector for the drop event
            #===================================================================
            main_widget = self.getMainWidget(self)
            new_children_list =[]
            parent_node.getParameters().deleteChild(parent_node.getParameter('nodeReference'))
            node_reference_param = parent_node.getParameters().createChildGroup('nodeReference')
            for index in range(parent_item.childCount()):
                item = parent_item.child(index)
                node = item.getRootNode()
                new_children_list.append(node)
                param_name = item.getItemType()
                main_widget.node.createNodeReference(parent_node,node,param_name,param=node_reference_param)

            main_widget.connectInsideGroup(new_children_list,parent_node)   
            
            if self.item.getItemType() == 'shot':

                item = self.item
                shot = item.text(0)
                shot_string = '%s%s'%(settings.SHOT_PREFIX, shot)
                root_node_list = getAllRootNodes(item,vs_node_list=[])
                for root_node in root_node_list:
                    vs_node = NodegraphAPI.GetNode(root_node.getParameter('nodeReference.vs_node').getValue(0))
                    shot_group = NodegraphAPI.GetNode(root_node.getParameter('nodeReference.shot_group').getValue(0))
                    port = vs_node.addInputPort(shot_string)
                    vs_node.getParameter('patterns.%s'%shot_string).setValue(str(shot),0)
                    port.connect(shot_group.getOutputPortByIndex(0))
                    
        
        #main_widget = self.getMainWidget(self)
        
        node = self.currentItem().getRootNode()

        old_parent = self.currentItem().parent()
        old_parent_node = old_parent.getRootNode()
        old_shot_node = NodegraphAPI.GetNode(old_parent_node.getParameter('nodeReference.shot_group').getValue(0))

        if self.current_parent:
            new_parent = self.current_parent
        else:
            new_parent = self.topLevelItem(0)
            self.currentItem().parent(new_parent)
        new_parent_node = new_parent.getRootNode()
        new_shot_node = NodegraphAPI.GetNode(new_parent_node.getParameter('nodeReference.shot_group').getValue(0))

        ## reset parameters
        disconnectItem(node,old_shot_node)

        ## set new parameters
        node.setParent(new_shot_node)
        
        ##### RESOLVE THE DROP EVENT...
        return_val = super( ShotBrowser, self ).dropEvent( event, *args, **kwargs )
        if self.currentItem().parent(): 
            new_parent.setExpanded(True)
            
        connectItem(new_parent,new_shot_node)
        return return_val
    
    def mouseReleaseEvent(self, event,*args, **kwargs):
        item = self.itemAt( event.pos() )
        if item:
            index = self.currentIndex()
            if index.column() == 0:
                pass
                #print index
            elif index.column() in [1,2]:
                ## load up version dir...
                if event.button() == 1:
                    main_widget = self.getMainWidget(self)
                    main_widget.displayVersions(display_type=str(item.getItemType()),column=index.column())

            return QtGui.QTreeWidget.mouseReleaseEvent(self, event,*args, **kwargs)

class ShotBrowserItem(QtGui.QTreeWidgetItem):
    #===========================================================================
    # creates items for the ShotBrowser TreeWidget, these items can be of type 'master','block','shot'
    #===========================================================================
    def __init__(self,parent,name='new_item',key_version='',shot_version='',block_version='',\
                 key_node=None,root_node=None,shot_node=None,unique_hash=None,item_type=None,expanded=False):
        super(ShotBrowserItem,self).__init__(parent)
        self.setText(0,name)
        self.setText(1,key_version)
        self.setText(2,shot_version)
        self.setText(3,block_version)
        self.item_type = item_type
        self.key_node = key_node
        self.root_node= root_node
        self.shot_node = shot_node
        self.block_version = block_version
        self.shot_version = shot_version
        self.key_version = key_version
        self.setExpanded(expanded)
        self.hash = self.createPublishDir(unique_hash=unique_hash)
        if item_type in ['master','block']:
            self.setFlags(self.flags() | QtCore.Qt.ItemIsEditable  )
        elif item_type == 'shot':
            self.setFlags(self.flags() & ~QtCore.Qt.ItemIsDropEnabled| QtCore.Qt.ItemIsDragEnabled )
            
    def getKeyNode(self):
        return self.key_node
    
    def setKeyNode(self,node):
        self.key_node = node
        
    def getShotNode(self):
        return self.shot_node
    
    def setShotNode(self,node):
        self.shot_node = node
        
    def getRootNode(self):
        return self.root_node
    
    def setRootNode(self,node):
        self.root_node = node
        
    def getMainWidget(self,widget):
        if isinstance(widget, GafferThreeSequenceEditor):
            return widget
        else:
            return self.getMainWidget(widget.parent())    
               
    def createPublishDir(self,unique_hash=None):
        #=======================================================================
        # generates a unique hash for the gaffer live group and then creates the 
        # directories on disk for them to be save into 
        #=======================================================================
        def checkHash(thash,location):
            thash = int(math.fabs(hash(str(thash))))
            
            if str(thash) in os.listdir(location):
                thash = int(math.fabs(hash(str(thash))))
                return checkHash(str(thash),location)
            return thash

        main_widget = self.getMainWidget(self.treeWidget())
        root_node = main_widget.node
        #shot = main_widget.getShot()
        sequence = main_widget.getSequence()
        if self.getItemType() == 'block':
            location = root_node.getParameter('publish_dir').getValue(0) + '/%s/blocks'%sequence

        elif self.getItemType() in ['master', 'shot']:
            location = root_node.getParameter('publish_dir').getValue(0) + '/%s/shots'%sequence
            
        if unique_hash:
            self.hash = unique_hash
        else:
            self.hash = hash(self.key_node.getName())
            self.hash = checkHash(self.hash,location)
            
            dir_list = ['gaffers','key','live_group','publish']
            block_location = '%s/%s'%(location,self.hash)
            os.mkdir(block_location)
            
            for dir_item in dir_list:
                os.mkdir(block_location + '/%s'%dir_item)
                os.mkdir(block_location + '/%s/live'%dir_item)

            
        self.publish_dir = '%s/%s'%(location,self.hash)
        return self.hash
        
    def getItemType(self):
        return self.item_type

    def setHash(self,unique_hash):
        self.hash = unique_hash

    def getHash(self):
        return self.hash
    
    def setPublishDir(self,publish_dir):
        self.publish_dir = publish_dir
        
    def getPublishDir(self):
        return self.publish_dir
    

'''
if __name__ == "__main__":
    import sys    
    app = QtGui.QApplication(sys.argv)
    
    g3 = GafferThreeSequenceEditor(None,None)
    g3.show()
    
    sys.exit(app.exec_())
'''
