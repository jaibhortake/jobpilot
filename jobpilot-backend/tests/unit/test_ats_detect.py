import pytest

from src.db.models import AtsType
from src.directory.ats_detect import detect


@pytest.mark.parametrize(
    ("url", "ats", "config"),
    [
        (
            "https://rockwellautomation.wd1.myworkdayjobs.com/en-US/External_Rockwell_Automation",
            AtsType.workday,
            {"tenant": "rockwellautomation", "wd": "wd1", "site": "External_Rockwell_Automation"},
        ),
        (
            "https://x.wd5.myworkdayjobs.com/en-US/Careers/login?redirect=1",
            AtsType.workday,
            {"tenant": "x", "wd": "wd5", "site": "Careers"},
        ),
        (
            "https://jpmc.fa.oraclecloud.com/hcmUI/CandidateExperience/en/sites/CX_1001/jobs",
            AtsType.oracle,
            {"host": "jpmc.fa.oraclecloud.com", "site": "CX_1001"},
        ),
        ("https://jobs.ashbyhq.com/cohere", AtsType.ashby, {"org": "cohere"}),
        ("https://careers.smartrecruiters.com/TSystems", AtsType.smartrecruiters,
         {"company": "TSystems"}),
        ("https://apply.careers.microsoft.com/careers?pid=1&domain=microsoft.com",
         AtsType.generic, {}),
    ],
)
def test_detect(url: str, ats: AtsType, config: dict[str, str]) -> None:
    assert detect(url) == (ats, config)
