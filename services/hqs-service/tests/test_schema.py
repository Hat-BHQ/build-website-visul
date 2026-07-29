from app.schemas import CreateRequest
def test_default_priority():
    assert CreateRequest(title='Printer issue').priority == 'normal'
