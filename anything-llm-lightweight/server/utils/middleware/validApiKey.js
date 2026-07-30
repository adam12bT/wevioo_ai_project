const { SystemSettings } = require("../../models/systemSettings");

// NOTE: API key auth disabled for this internal/single-user fork —
// there is no admin panel left to generate a key from, and this API
// is only ever called by our own internal agent pipeline.
// If this service is ever exposed beyond localhost/your internal network,
// re-enable a real auth check here before that happens.
async function validApiKey(request, response, next) {
  const multiUserMode = await SystemSettings.isMultiUserMode();
  response.locals.multiUserMode = multiUserMode;
  next();
}

module.exports = {
  validApiKey,
};
