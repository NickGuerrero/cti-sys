from fastapi import APIRouter, status

router = APIRouter()

@router.post("", status_code=status.HTTP_200_OK)
def export_applicants_to_canvas(

):
    pass
