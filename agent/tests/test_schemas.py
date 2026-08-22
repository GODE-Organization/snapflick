from snapflick.models.schemas import Job, JobStatus, ProductSheet


def test_campos_opcionales_pueden_ser_none():
    s = ProductSheet(name="Harina PAN", description="Harina de maíz precocida.")
    assert s.brand is None
    assert s.confidence == "medium"
    assert s.keywords == []


def test_job_inicia_pendiente():
    assert Job(id="abc").status is JobStatus.PENDING
