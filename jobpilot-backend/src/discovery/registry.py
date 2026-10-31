from src.db.models import AtsType
from src.discovery.base import SourceReader
from src.discovery.readers.ashby import AshbyReader
from src.discovery.readers.generic import GenericReader
from src.discovery.readers.greenhouse import GreenhouseReader
from src.discovery.readers.icims import IcimsReader
from src.discovery.readers.lever import LeverReader
from src.discovery.readers.oracle import OracleReader
from src.discovery.readers.smartrecruiters import SmartRecruitersReader
from src.discovery.readers.workday import WorkdayReader

READERS: dict[AtsType, SourceReader] = {
    r.ats_type: r
    for r in (
        WorkdayReader(), OracleReader(), SmartRecruitersReader(), AshbyReader(),
        GreenhouseReader(), LeverReader(), IcimsReader(), GenericReader(),
    )
}


def get_reader(ats: AtsType) -> SourceReader | None:
    return READERS.get(ats)
