import csv

def get_application_documents():
    pass

def generate_users_csv():
    with open("users.csv", "w", newline="") as users_csv:
        writer = csv.writer(users_csv, dialect="excel")
        writer.writerow([""])
    pass

def generate_unterview_enrollments_csv():
    pass

def import_sis_csv():
    pass

def get_unterview_enrollments():
    # may require pagination for parsing through the enrollments
    pass

def patch_applicants_with_unterview(application_documents, unterview_enrollments):
    pass

def add_applicants_to_canvas():
    # validate params from request

    # fetch documents
    application_documents = get_application_documents()
    # if no documents -> error out

    # generate CSVs (users.csv and enrollments.csv)
    users_csv = generate_users_csv()
    enrollments_csv = generate_unterview_enrollments_csv()

    import_sis_csv(users_csv)
    import_sis_csv(enrollments_csv)

    # fetch enrollments for current section (Target Summer 2025)
    unterview_enrollments = get_unterview_enrollments()

    # update documents with Canvas information
    patch_applicants_with_unterview(
        application_documents,
        unterview_enrollments,
        )

    """
    last_canvas_batch [boolean]             -> 
    canvas_id [int]                         -> 
    added_unterview_course [boolean]        -> True (unless there is an ID)
    next_steps_sent [boolean]
    accessed_unterview [boolean]
    commitment_quiz_completed [boolean]
    master_added [boolean]
    """

    # respond with success, number of updated documents, batch date

    pass
