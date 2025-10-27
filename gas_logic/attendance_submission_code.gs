// Rename the question titles to correct form submission schema
// Use IDs from above and enter them here before enabling the form trigger
// Helper functions & regex
const qids = {
  program: 0,
  session_type: 0,
  session_date: 0,
  session_start_time: 0,
  session_end_time: 0,
  link_type: 0,
  link: 0
}

function onFormSubmit(e) {
  let submission = e.response;
  let form = e.source;

  const data = {
    owner: sanitize(submission.getRespondentEmail()).toLowerCase(),
    program: nullify(get_response(form, submission, qids.program)),
    session_type: nullify(get_response(form, submission, qids.session_type)),
    session_date: nullify(get_response(form, submission, qids.session_date)),
    session_start_time: nullify(get_response(form, submission, qids.session_start_time)),
    session_end_time: nullify(get_response(form, submission, qids.session_end_time)),
    link_type: nullify(get_response(form, submission, qids.link_type)),
    link: nullify(get_response(form, submission, qids.link))
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
  let msg = UrlFetchApp.fetch(url + "/api/students/create-attendance-entry", options);

  // Log details in case of errors
  console.log(msg.getResponseCode());
  if(msg.getResponseCode() > 399){
    console.log(msg.getContentText())
  }
}
