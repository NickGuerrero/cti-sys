// Set question IDs before form handling
// Also, run before to ensure that scripts have proper permissions
function logQuestionIDs() {
  /** Get the question ids manually, use this to create the qids object */
  const form = FormApp.getActiveForm();
  const items = form.getItems();

  const question_map = new Map();
  items.forEach(item => {
    question_map.set(item.getTitle().replaceAll(/\s/g, ""), item.getId());
  });

  // JSON conversion for neatness
  const result = JSON.stringify(Object.fromEntries(question_map), null, "\t");
  console.log(result);
}