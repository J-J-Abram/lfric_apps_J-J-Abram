# -----------------------------------------------------------------------------
#  (C) Crown copyright 2023 Met Office. All rights reserved.
#  The file LICENCE, distributed with this code, contains details of the terms
#  under which the code may be used.
# -----------------------------------------------------------------------------


'''
This file contains frequently used transformations to simplify
their application in PSyclone optimisations scripts.

'''
from psyclone.domain.lfric import LFRicConstants
from psyclone.transformations import (Dynamo0p3ColourTrans,
                                      Dynamo0p3OMPLoopTrans,
                                      OMPParallelTrans,
                                      Dynamo0p3RedundantComputationTrans)


# List of allowed 'setval_*' built-ins for redundant computation transformation
SETVAL_BUILTINS = ["setval_c"]


# -----------------------------------------------------------------------------
def redundant_computation_setval(psy):
    '''
    Applies the redundant computation transformation to loops over DoFs
    for the initialision built-ins, 'setval_*'.

    To reduce MPI communications, current PSyclone-LFRic strategy does not
    apply halo swaps on input arguments to kernels with increment
    operations on continuous fields such as 'GH_INC'. For such kernels,
    PSy-layer code needs to loop into the halo to correctly compute owned
    DoFs on the boundary between the halo and the domain. Therefore values
    of the remaining DoFs in the first halo cell need to be initialised to
    values that will not induce numerical errors.

    By default, the initialisation 'setval_*' built-ins do not initialise
    into the halos. This transform causes them to do so, and so permits
    developers to set safe values in halos.

    :param psy: the PSy object that PSyclone has constructed for the
                'invoke'(s) found in the Algorithm file.
    :type psy: :py:class:`psyclone.dynamo0p3.DynamoPSy`

    :raises Exception: if there is more than one built-in call per DoF loop.

    '''
    # Import redundant computation transformation
    rtrans = Dynamo0p3RedundantComputationTrans()

    # Loop over all the Invokes in the PSy object
    for invoke in psy.invokes.invoke_list:

        schedule = invoke.schedule

        # Make setval_* built-ins compute redundantly to the level-1 halo
        # if they are in their own loop
        for loop in schedule.loops():
            if loop.iteration_space == "dof":
                if len(loop.kernels()) != 1:
                    raise Exception(
                        f"Expecting loop to contain 1 call but found "
                        f"'{len(loop.kernels())}'")
                if loop.kernels()[0].name in SETVAL_BUILTINS:
                    rtrans.apply(loop, options={"depth": 1})


# -----------------------------------------------------------------------------
def colour_loops(psy):
    '''
    Applies the colouring transformation to all applicable loops.
    It creates the instance of `Dynamo0p3ColourTrans` only once.

    :param psy: the PSy object that PSyclone has constructed for the
                'invoke'(s) found in the Algorithm file.
    :type psy: :py:class:`psyclone.dynamo0p3.DynamoPSy`

    '''
    const = LFRicConstants()
    ctrans = Dynamo0p3ColourTrans()

    # Loop over all the Invokes in the PSy object
    for invoke in psy.invokes.invoke_list:

        schedule = invoke.schedule

        # Colour loops over cells unless they are on discontinuous
        # spaces or over DoFs
        for loop in schedule.loops():
            if loop.iteration_space == "cell_column" \
                and loop.field_space.orig_name \
                    not in const.VALID_DISCONTINUOUS_NAMES:
                ctrans.apply(loop)


# -----------------------------------------------------------------------------
def openmp_parallelise_loops(psy):
    '''
    Applies OpenMP Loop transformation to each applicable loop.

    :param psy: the PSy object that PSyclone has constructed for the
                'invoke'(s) found in the Algorithm file.
    :type psy: :py:class:`psyclone.dynamo0p3.DynamoPSy`

    '''
    otrans = Dynamo0p3OMPLoopTrans()
    oregtrans = OMPParallelTrans()

    # Loop over all the Invokes in the PSy object
    for invoke in psy.invokes.invoke_list:

        schedule = invoke.schedule

        # Add OpenMP to loops unless they are over colours or are null
        for loop in schedule.loops():
            if loop.loop_type not in ["colours", "null"]:
                oregtrans.apply(loop)
                otrans.apply(loop, options={"reprod": True})


# -----------------------------------------------------------------------------
def view_transformed_schedule(psy):
    '''
    Provides view of transformed Invoke schedule in the PSy-layer.

    :param psy: the PSy object that PSyclone has constructed for the
                'invoke'(s) found in the Algorithm file.
    :type psy: :py:class:`psyclone.dynamo0p3.DynamoPSy`

    '''
    setval_count = 0

    # Loop over all the Invokes in the PSy object
    for invoke in psy.invokes.invoke_list:

        print(f"Transformed invoke '{invoke.name}' ...")
        schedule = invoke.schedule

        # Count instances of setval_* built-ins
        for loop in schedule.loops():
            if loop.iteration_space == "dof":
                if loop.kernels()[0].name in SETVAL_BUILTINS:
                    setval_count += 1

        # Take a look at what we have done
        print(f"Found {setval_count} {SETVAL_BUILTINS} calls")
        print(schedule.view())
