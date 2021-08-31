###############################################################################
# ProteusLib Copyright (c) 2021, The Regents of the University of California,
# through Lawrence Berkeley National Laboratory, Oak Ridge National
# Laboratory, National Renewable Energy Laboratory, and National Energy
# Technology Laboratory (subject to receipt of any required approvals from
# the U.S. Dept. of Energy). All rights reserved.
#
# Please see the files COPYRIGHT.md and LICENSE.md for full copyright and license
# information, respectively. These files are also available online at the URL
# "https://github.com/nawi-hub/proteuslib/"
#
###############################################################################

"""Pretreatment flowsheet components"""

from pyomo.environ import ConcreteModel, TransformationFactory
from pyomo.network import Arc
from idaes.core import FlowsheetBlock
from idaes.generic_models.unit_models import Feed, Separator, Mixer
from idaes.generic_models.unit_models.separator import SplittingType, EnergySplittingType
from idaes.core.util.scaling import calculate_scaling_factors
from idaes.core.util.initialization import propagate_state
from proteuslib.flowsheets.full_treatment_train.example_flowsheets import feed_block
from proteuslib.flowsheets.full_treatment_train.example_models import unit_separator, unit_ZONF, property_models
from proteuslib.flowsheets.full_treatment_train.util import solve_with_user_scaling, check_dof

def build_pretreatment_NF(m, has_bypass=True, NF_type='ZO', NF_base='ion'):
    """
    Builds NF pretreatment including specified feed and auxiliary equipment.
    The built components are initialized based on default values.
    Arguments:
        has_bypass: True or False, default = True
        NF_type: 'Sep' or 'ZO', default = 'ZO'
        NF_base: 'ion' or 'salt', default = 'ion'
    """
    pretrt_port = {}
    optarg = {'nlp_scaling_method': 'user-scaling'}
    prop = property_models.get_prop(m, base=NF_base)

    # build feed
    feed_block.build_feed(m, base=NF_base)

    # build NF
    if NF_type == 'Sep':
        unit_separator.build_SepNF(m, base=NF_base)
    elif NF_type == 'ZO':
        unit_ZONF.build_ZONF(m, base=NF_base)
    else:
        raise ValueError('Unexpected model type {NF_type} provided to build_NF_no_bypass'
                         ''.format(NF_type=NF_type))

    if has_bypass:
        # build auxiliary units
        m.fs.splitter = Separator(default={
            "property_package": prop,
            "outlet_list": ['pretreatment', 'bypass'],
            "split_basis": SplittingType.totalFlow,
            "energy_split_basis": EnergySplittingType.equal_temperature})
        m.fs.mixer = Mixer(default={
            "property_package": prop,
            "inlet_list": ['pretreatment', 'bypass']})

        # connect models
        m.fs.s_pretrt_feed_splitter = Arc(source=m.fs.feed.outlet, destination=m.fs.splitter.inlet)
        m.fs.s_pretrt_splitter_mixer = Arc(source=m.fs.splitter.bypass, destination=m.fs.mixer.bypass)
        m.fs.s_pretrt_splitter_NF = Arc(source=m.fs.splitter.pretreatment, destination=m.fs.NF.inlet)
        m.fs.s_pretrt_NF_mixer = Arc(source=m.fs.NF.permeate, destination=m.fs.mixer.pretreatment)

        # specify (NF and feed is already specified, mixer has 0 DOF, splitter has 1 DOF)
        # splitter
        m.fs.splitter.split_fraction[0, 'bypass'].fix(0.1)

        # scaling (NF and RO models and translator are already scaled)
        calculate_scaling_factors(m.fs.splitter)
        calculate_scaling_factors(m.fs.mixer)

        # initialize
        m.fs.feed.initialize(optarg=optarg)
        propagate_state(m.fs.s_pretrt_feed_splitter)
        m.fs.splitter.initialize(optarg=optarg)
        propagate_state(m.fs.s_pretrt_splitter_mixer)
        propagate_state(m.fs.s_pretrt_splitter_NF)
        if NF_type != 'Sep':  # IDAES error when NF is a separator TODO: discuss with Andrew
            m.fs.NF.initialize(optarg=optarg)
        propagate_state(m.fs.s_pretrt_NF_mixer)
        m.fs.mixer.initialize(optarg=optarg)

        # inlet/outlet ports for pretreatment
        pretrt_port['out'] = m.fs.mixer.outlet
        pretrt_port['waste'] = m.fs.NF.retentate

    else:  # no bypass
        # build auxiliary units (none)

        # connect models
        m.fs.s_pretrt_feed_NF = Arc(source=m.fs.feed.outlet, destination=m.fs.NF.inlet)

        # specify (NF and feed are already specified)

        # scaling (NF and feed are already scaled)

        # initialize
        m.fs.feed.initialize(optarg=optarg)
        propagate_state(m.fs.s_pretrt_feed_NF)
        if NF_type != 'Sep':  # IDAES error when NF is a separator TODO: discuss with Andrew
            m.fs.NF.initialize(optarg=optarg)

        # inlet/outlet ports for pretreatment
        pretrt_port['out'] = m.fs.NF.permeate
        pretrt_port['waste'] = m.fs.NF.retentate

    return pretrt_port


def solve_build_pretreatment_NF(has_bypass=True, NF_type='ZO', NF_base='ion'):
    m = ConcreteModel()
    m.fs = FlowsheetBlock(default={"dynamic": False})
    property_models.build_prop(m, base=NF_base)
    build_pretreatment_NF(m, has_bypass=has_bypass, NF_type=NF_type, NF_base=NF_base)

    TransformationFactory("network.expand_arcs").apply_to(m)
    check_dof(m)
    solve_with_user_scaling(m, tee=True, fail_flag=True)


if __name__ == "__main__":
    solve_build_pretreatment_NF(has_bypass=True, NF_type='ZO', NF_base='ion')