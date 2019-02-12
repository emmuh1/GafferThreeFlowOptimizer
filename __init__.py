# Copyright (c) 2012 The Foundry Visionmongers Ltd. All Rights Reserved.

import Katana
import v2 as GafferThreeSequence

if GafferThreeSequence:
    PluginRegistry = [
        ("SuperTool", 2, "GafferThreeFlowOptimizer",
                (GafferThreeSequence.GafferThreeSequenceNode,
                        GafferThreeSequence.GetEditor)),
    ]
