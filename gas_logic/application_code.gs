// Rename the question titles to correct form submission schema
// Use IDs from above and enter them here before enabling the form trigger
// The fields are listed in the order of the current quiz (9/24/2025)
const qids = {
	HEADER: 0,
	fname: 0,
	pname: 0,
	lname: 0,
	phone: 0,
	birthday: 0,
	returning: 0,
	institution: 0,
	ca_region: 0,
	academic_year: 0,
	grad_year: 0,
	summers_left: 0,
	cs_exp: 0,
	cs_courses: 0,
	math_courses: 0,
	EXPECTATION_HEADER: 0,
	program_expectation: 0,
	career_outlook: 0,
	academic_goals: 0,
	DEMOGRAPHIC_HEADER: 0,
	first_gen: 0,
	gender: 0,
	race_ethnicity: 0,
	financial_need: 0,
	heard_about: 0,
	LAST_STEP: 0,
	CONFIRMATION: 0
};

// Date formatting
const date_MDY = /([1-3]?\d)(\/|-)([1-3]?\d)(\/|-)(\d\d\d\d)/g;
const date_YMD = /$5-$1-$3/g;

function onFormSubmit(e){
  // Declare form and submission for clarity
  let submission = e.response;
  let form = e.source;
  const data = {
    email: sanitize(submission.getRespondentEmail()).toLowerCase(),
    fname: nullify(get_response(form, submission, qids.fname)),
    pname: nullify(get_response(form, submission, qids.pname)),
    lname: nullify(get_response(form, submission, qids.lname)),
    phone: nullify(get_response(form, submission, qids.phone)),
    birthday: nullify(get_response(form, submission, qids.birthday).replace(date_MDY, date_YMD)),
    returning: nullify(get_response(form, submission, qids.returning) == "Yes" ? true : false),
    institution: nullify(get_response(form, submission, qids.institution)),
    ca_region: nullify(get_response(form, submission, qids.ca_region)),
    academic_year: nullify(get_response(form, submission, qids.academic_year).replace(/(\D+)/g, "")),
    grad_year: nullify(get_response(form, submission, qids.grad_year)),
    summers_left: nullify(get_response(form, submission, qids.summers_left).replace(/(\D+)/g, "")),
    cs_exp: nullify(get_response(form, submission, qids.cs_exp)  == ("Yes" | "Currently Taking") ? true : false),
    cs_courses: nullify(get_response(form, submission, qids.cs_courses)),
    math_courses: nullify(get_response(form, submission, qids.math_courses)),
    program_expectation: nullify(get_response(form, submission, qids.program_expectation)),
    career_outlook: nullify(get_response(form, submission, qids.career_outlook)),
    academic_goals: nullify(get_response(form, submission, qids.academic_goals)),
    first_gen: nullify(get_response(form, submission, qids.first_gen)  == "Yes" ? true : false),
    gender: nullify(get_response(form, submission, qids.gender)),
    race_ethnicity: nullify(get_response(form, submission, qids.race_ethnicity)),
    financial_need: nullify(get_response(form, submission, qids.financial_need)),
    heard_about: nullify(get_response(form, submission, qids.heard_about))
  };

  // Send packet to server
  const env = PropertiesService.getScriptProperties();
  const url = env.getProperty('SERVER_BASE_URL');
  const auth_key = env.getProperty('AUTH_KEY');

  const options = {
    method: "post",
    headers: {Authorization: "Bearer " + auth_key},
    contentType: "application/json",
    payload: JSON.stringify(data)
  };
  let msg = UrlFetchApp.fetch(url + "/api/applications", options);

  // Log details in case of errors
  console.log(msg.getResponseCode());
  if(msg.getResponseCode() > 399){
    console.log(msg.getContentText())
  }
}