from decimal import Decimal

from tp_drawer.models import Layer, Project, ProjectInfo, TrialPit, project_from_dict, project_to_dict


def test_project_to_dict_and_back_round_trips():
    project = Project(
        info=ProjectInfo(date="02/07/26", project_number="AMR 15414"),
        pits=[
            TrialPit(
                number="1",
                layers=[Layer(name="Topsoil", thickness_in=Decimal("14"), description="Dark brown silt.")],
                groundwater_depth_in=Decimal("86"),
                extra_note="Note.",
                walls_stable=False,
            ),
            TrialPit(number="2", layers=[], groundwater_depth_in=None),
        ],
    )

    round_tripped = project_from_dict(project_to_dict(project))

    assert round_tripped == project
