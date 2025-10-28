// Rename the question titles to correct form submission schema
// Use IDs from above and enter them here before enabling the form trigger
const qids = {
  alt_emails: 0,
  remove_emails: 0,
  change_primary: 0
}

function onFormSubmit(e) {
  let submission = e.response;
  let form = e.source;

  // Primary email function, only allow switching to the user submission email address
  let new_primary_email = "";
  if(get_response(form, submission, qids.change_primary) == "Yes"){
    new_primary_email = sanitize(submission.getRespondentEmail()).toLowerCase();
  }

  const data = {
    google_form_email: sanitize(submission.getRespondentEmail()).toLowerCase(),
    primary_email: new_primary_email,
    alt_emails: nullify(get_response(form, submission, qids.alt_emails).toLowerCase()),
    remove_emails: nullify(get_response(form, submission, qids.remove_emails).toLowerCase())
  };
  
  // Set-up Arrays
  if(data.alt_emails != null){
    data.alt_emails = data.alt_emails.split(/\s*,\s*/g);
  } else {
    data.alt_emails = [];
  }
  if(data.remove_emails != null){
    data.remove_emails = data.remove_emails.split(/\s*,\s*/g);
  } else {
    data.remove_emails = [];
  }

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
  let msg = UrlFetchApp.fetch(url + "/api/students/alternate-emails", options);

  // Log details in case of errors
  console.log(msg.getResponseCode());
  if(msg.getResponseCode() > 399){
    console.log(msg.getContentText())
  }
}