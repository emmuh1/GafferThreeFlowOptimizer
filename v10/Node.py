
# Copyright (c) 2012 The Foundry Visionmongers Ltd. All Rights Reserved.

from Katana import NodegraphAPI, Utils, UniqueName, DrawingModule


import logging, settings, os

log = logging.getLogger("Test.Node")


class GafferThreeSequenceNode(NodegraphAPI.SuperTool):
    
    def __init__(self,populate=True):
        NodegraphAPI.SetNodeShapeAttr(self, 'basicDisplay', 1)
        def _populate():

            def createNodeParam(node,param_name):
                param = self.getParameters().createChildString(param_name,'')
                param.setExpressionFlag(True)
                param.setExpression('@%s'%node.getName())
            
            #===================================================================
            # CREATE NODES
            #===================================================================
            
            def AddGlobalGraphStateVariable(name, options):
                from Katana import  NodegraphAPI
                
                variablesGroup = NodegraphAPI.GetRootNode().getParameter('variables')
   
                variableParam = variablesGroup.createChildGroup(name)
                variableParam.createChildNumber('enable', 1)
                variableParam.createChildString('value', options[0])
                optionsParam = variableParam.createChildStringArray('options', len(options))
                for optionParam, optionValue in zip(optionsParam.getChildren(), options):
                    optionParam.setValue(optionValue, 0)
                return variableParam.getName()

    
            
            node_list = []
            self.addOutputPort('out')
            self.addInputPort('in')
            self.getSendPort('in').connect(self.getReturnPort('out'))
            self.sequence_lg = self.createBlockGroup(self, 'sequence')
            self.sequence_lg.getParameter('hash').setValue('master',0)
            self.shot_lg = NodegraphAPI.GetNode(self.sequence_lg.getParameter('nodeReference.shot_group').getValue(0))
            
            node_list.append(self.sequence_lg)

            
            Utils.EventModule.ProcessAllEvents()

            self.connectInsideGroup(node_list, self)
            
            
            #===================================================================
            # SET UP PARAMETERS
            #===================================================================
            self.createNodeReference(self,self.sequence_lg,'sequence_node',param=None)
            self.createNodeReference(self,self.shot_lg,'shot_node',param=None)
            self.gaffer_three_display_param = self.getParameters().createChildString('gaffer_display','')
            self.gaffer_three_display_param.setHintString(repr({'widget':'teleparam'}))
            
            self.publish_dir = self.getParameters().createChildString('publish_dir',settings.SEQUENCE_PATH)
            
            if NodegraphAPI.GetNode('rootNode').getParameter('variables.sequence'):
                self.sequence = NodegraphAPI.GetNode('rootNode').getParameter('variables.sequence.value').getValue(0)
            else:
                AddGlobalGraphStateVariable('sequence',['default'])
                self.sequence = 'default'
            if not os.path.exists(settings.SEQUENCE_PATH + '/%s'%self.sequence):
                #print 'not' , settings.SEQUENCE_PATH + '/%s'%sequence
                os.mkdir(settings.SEQUENCE_PATH + '/%s'%self.sequence)
                os.mkdir(settings.SEQUENCE_PATH + '/%s/blocks'%self.sequence)
                os.mkdir(settings.SEQUENCE_PATH + '/%s/shots'%self.sequence)
            self.publish_dir.setHintString(repr({'widget': 'fileInput'}))
            '''
            version_options = []
            if NodegraphAPI.GetNode('rootNode').getParameter('variables.sequence'):
                sequence = NodegraphAPI.GetNode('rootNode').getParameter('variables.sequence.value').getValue(0)
                if os.path.isdir('%s/%s/sequence/%s'%(settings.SEQUENCE_PATH,sequence,sequence)):
                    #print '%s/light/%s/sequence/%s'%(settings.SEQUENCE_PATH,sequence,sequence)
                    version_options = os.listdir('%s/%s/sequence/%s'%(settings.SEQUENCE_PATH,sequence,sequence))
                    
            self.sequence_param = self.getParameters().createChildString('version','v001')
            self.sequence_param.setHintString(repr({'widget': 'popup', 'options': version_options}))
            
            sequence_options = []
            #shot_options = []
            if NodegraphAPI.GetRootNode().getParameter('variables.sequence'):
                for child in NodegraphAPI.GetNode('rootNode').getParameter('variables.sequence.options').getChildren():
                    sequence_options.append(child.getValue(0))
            '''
            #if NodegraphAPI.GetRootNode().getParameter('variables.shot'):
                #for child in NodegraphAPI.GetNode('rootNode').getParameter('variables.shot.options').getChildren():
                    #shot_options.append(child.getValue(0))
                    
            self.sequence_param = self.getParameters().createChildString('sequence',self.sequence)
            self.sequence_param.setHintString(repr({'readOnly': 'True'}))
            #self.sequence_param.setHintString(repr({'widget': 'popup', 'options': sequence_options}))
            
            #self.sequence_param = self.getParameters().createChildString('shot','030')
            #self.sequence_param.setHintString(repr({'widget': 'popup', 'options': shot_options}))
            
            self.populateShots()
        if populate == True:
            _populate()
        elif populate == False:
            pass

    def createNodeReference(self,node,node_ref,param_name,param=None):
        if not param:
            param = node.getParameters()
        new_param = param.createChildString(param_name,'')
        new_param.setExpressionFlag(True)
        new_param.setExpression('@%s'%node_ref.getName())
        return new_param
    
    def createVariableSwitch(self,root_node):
        vs_node = NodegraphAPI.CreateNode('VariableSwitch',root_node)
        vs_node.addInputPort('default')
        vs_node.getParameter('variableName').setValue('shot',0)
        return vs_node
    
    def createBlockGroup(self,root_node,name=None):
        if not name:
            name = 'block_01'
        group_node = NodegraphAPI.CreateNode('Group',root_node)
        group_node.setName(name)
        
        group_params = group_node.getParameters().createChildGroup('nodeReference')
        group_node.addOutputPort('out')
        group_node.addInputPort('in')
        
        key_group = self.createGroup(group_node,name='key')
        shot_group = self.createGroup(group_node,name='shots')
        vs_node = self.createVariableSwitch(group_node)
        add_params_node_list = [group_node, key_group, shot_group]
        #=======================================================================
        # PARAMETERS
        #=======================================================================
        self.createNodeReference(group_node,key_group,'key_node',param=group_params)
        self.createNodeReference(group_node,shot_group,'shot_group',param=group_params)
        self.createNodeReference(group_node,vs_node,'vs_node',param=group_params)
        self.createNodeReference(root_node,group_node,'block00',param=root_node.getParameter('nodeReference'))
        
        for node in add_params_node_list:
            version = node.getParameters().createChildString('version','')
            unique_hash = node.getParameters().createChildString('hash','')
            node.getParameters().createChildString('expanded','False')
        #=======================================================================
        # CONNECT
        #=======================================================================
        self.connectInsideGroup([key_group,shot_group,vs_node], group_node)
        group_node.getSendPort('in').connect(vs_node.getInputPortByIndex(0))
        
        return group_node
    
    def createGroup(self,root_node,shot_stack=None,name=''):
        #=======================================================================
        # builds live group
        #=======================================================================
        shot_live_group = NodegraphAPI.CreateNode('Group',root_node)
        shot_live_group.setName(name)
        shot_live_group.addOutputPort('out')
        shot_live_group.addInputPort('in')
        shot_live_group.getSendPort('in').connect(shot_live_group.getReturnPort('out'))
        shot_live_group.getParameters().createChildGroup('nodeReference')
        return shot_live_group
    
    def createShotGroup(self,root_node=None,shot=None):
        #=======================================================================
        # variable enable group --> live group --> live group --> gaffer three
        # variable enable group holds multiple gaffer threes... by default it will create none
        #=======================================================================
        sequence = self.getParameter('sequence').getValue(0)
        #sequence = self.sequence
        shot_string = '%s%s'%(settings.SHOT_PREFIX, shot)
        shot_VEG = NodegraphAPI.CreateNode('VariableEnabledGroup',root_node)
        shot_VEG.addOutputPort('out')
        shot_VEG.addInputPort('in')
        shot_VEG.getParameter('variableName').setValue('shot',0)
        shot_VEG.getParameter('pattern').setValue(shot,0)
        shot_VEG.setName(shot_string)
        shot_live_group = self.createGroup(shot_VEG,name=shot)

        sequence_param = root_node.getParameter('nodeReference').createChildString(shot_string,'')
        sequence_param.setExpressionFlag(True)
        sequence_param.setExpression('@%s'%shot_VEG.getName())

        
        shot_live_group.getInputPortByIndex(0).connect(shot_VEG.getSendPort('in'))
        shot_live_group.getOutputPortByIndex(0).connect(shot_VEG.getReturnPort('out'))
        shot_live_group.getParameters().createChildString('version','')
        shot_live_group.getParameters().createChildString('hash','%s_%s'%(sequence,shot))
        
        publish_dir = self.getParameter('publish_dir').getValue(0) + '/%s/shots/%s_%s'%(sequence,sequence,shot)
        
        if not os.path.exists(publish_dir):
            dir_list = ['gaffers','key','live_group','publish']
            os.mkdir(publish_dir)
            for dir_item in dir_list:
                os.mkdir(publish_dir + '/%s'%dir_item)
                os.mkdir(publish_dir + '/%s/live'%dir_item)
        return shot_VEG
    
    def populateShots(self):
        root = NodegraphAPI.GetRootNode()
        node_list = []
        if root.getParameter('variables.shot'):
            # VEG --> LG --> GS 
            shots = root.getParameter('variables.shot.options')
            for child in shots.getChildren():
                group_node = self.createShotGroup(root_node=self.shot_lg,shot=child.getValue(0))
                node_list.append(group_node)
            self.connectInsideGroup(node_list,self.shot_lg)
                
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
            
            
#node= GafferThreeSequenceNode()