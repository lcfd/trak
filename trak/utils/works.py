from trak.works.models import Work


def change_work_field(work: Work, parameter: str, value):
    tpl_dict = work._asdict()
    tpl_dict[parameter] = value
    return Work(**tpl_dict)
