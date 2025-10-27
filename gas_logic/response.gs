function nullify(s){
  /** Turn empty strings to null to ensure form compatbility */
  return s === "" ? null : s;
}

function get_response(current_form, quiz_response, question_id, lower_arr = false){
  /**
   * Get response from form packet
   * param current_form: Form object, the form where the question originated from
   * param quiz_response: FormResponse object, the response from the form
   * param question_id: Integer, the question id that has the form response
   * param lower_arr: Boolean, convert string array elements to lowercase
   * 
   * Notes:
   * - If the user didn't submit a response for a question, it's not in the form response
   * - Form objects will handle the Array creation, no need to split for multiple-answer qs
   * - Google Form sanitization is not mentioned in docs, always assume the data is unsafe
   * - If we expect strings and no response is found, we return empty to ensure correct operations
   */
  // Fetch the response, if possible
  let response_question = quiz_response.getResponseForItem(
    current_form.getItemById(question_id)
  );
  response = response_question ? response_question.getResponse() : "";

  // Sanitize arrays in place, do not keep the dirty copy with map()
  if(Array.isArray(response)){
    for(let i = 0; i < response.length; i++){
      response[i] = sanitize(response[i]);
      if(lower_arr){
        reponse[i] = response[i].toLowerCase(); // Used primarily for email addresses
      }
    }
    return response;
  } else {
    return sanitize(response);
  }
}