from trakcli.works.models import Work


def change_value(work: Work, parameter: str, value):
    tpl_dict = work._asdict()
    tpl_dict[parameter] = value
    return Work(**tpl_dict)
