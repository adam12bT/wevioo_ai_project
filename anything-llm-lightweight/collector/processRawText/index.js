const { v4 } = require("uuid");
const { writeToServerDocuments } = require("../utils/files");
const { tokenizeString } = require("../utils/tokenizer");
const { default: slugify } = require("slugify");

// Will remove the last .extension from the input
// and stringify the input + move to lowercase.
function stripAndSlug(input) {
  if (!input.includes(".")) return slugify(input, { lower: true });
  return slugify(input.split(".").slice(0, -1).join("-"), { lower: true });
}

const METADATA_KEYS = {
  possible: {
    url: ({ url, title }) => {
      let validUrl;
      try {
        const u = new URL(url);
        validUrl = ["https:", "http:"].includes(u.protocol);
      } catch {}

      if (validUrl) return `web://${url.toLowerCase()}.website`;
      return `file://${stripAndSlug(title)}.txt`;
    },
    title: ({ title }) => `${stripAndSlug(title)}.txt`,
    docAuthor: ({ docAuthor }) => {
      return typeof docAuthor === "string" ? docAuthor : "no author specified";
    },
    description: ({ description }) => {
      return typeof description === "string"
        ? description
        : "no description found";
    },
    docSource: ({ docSource }) => {
      return typeof docSource === "string" ? docSource : "no source set";
    },
    chunkSource: ({ chunkSource, title }) => {
      return typeof chunkSource === "string"
        ? chunkSource
        : `${stripAndSlug(title)}.txt`;
    },
    published: ({ published }) => {
      if (isNaN(Number(published))) return new Date().toLocaleString();
      return new Date(Number(published)).toLocaleString();
    },
    externalId: ({ externalId }) =>
      typeof externalId === "string" ? externalId : null,
    sourceFilename: ({ sourceFilename }) =>
      typeof sourceFilename === "string" ? sourceFilename : null,
    documentType: ({ documentType }) =>
      typeof documentType === "string" ? documentType : null,
    page: ({ page }) =>
      page !== null && page !== undefined && Number.isInteger(Number(page))
        ? Number(page)
        : null,
    section: ({ section }) =>
      typeof section === "string" ? section : null,
    contentType: ({ contentType }) =>
      typeof contentType === "string" ? contentType : null,
    extractionMethod: ({ extractionMethod }) =>
      typeof extractionMethod === "string" ? extractionMethod : null,
    layoutOrder: ({ layoutOrder }) =>
      layoutOrder !== null &&
      layoutOrder !== undefined &&
      Number.isInteger(Number(layoutOrder))
        ? Number(layoutOrder)
        : null,
    bbox: ({ bbox }) =>
      Array.isArray(bbox) &&
      bbox.length === 4 &&
      bbox.every((value) => Number.isFinite(Number(value)))
        ? bbox.map(Number)
        : null,
  },
};

async function processRawText(textContent, metadata) {
  console.log(`-- Working Raw Text doc ${metadata.title} --`);
  if (!textContent || textContent.length === 0) {
    return {
      success: false,
      reason: "textContent was empty - nothing to process.",
      documents: [],
    };
  }

  const data = {
    id: v4(),
    url: METADATA_KEYS.possible.url(metadata),
    title: METADATA_KEYS.possible.title(metadata),
    docAuthor: METADATA_KEYS.possible.docAuthor(metadata),
    description: METADATA_KEYS.possible.description(metadata),
    docSource: METADATA_KEYS.possible.docSource(metadata),
    chunkSource: METADATA_KEYS.possible.chunkSource(metadata),
    published: METADATA_KEYS.possible.published(metadata),
    externalId: METADATA_KEYS.possible.externalId(metadata),
    sourceFilename: METADATA_KEYS.possible.sourceFilename(metadata),
    documentType: METADATA_KEYS.possible.documentType(metadata),
    page: METADATA_KEYS.possible.page(metadata),
    section: METADATA_KEYS.possible.section(metadata),
    contentType: METADATA_KEYS.possible.contentType(metadata),
    extractionMethod: METADATA_KEYS.possible.extractionMethod(metadata),
    layoutOrder: METADATA_KEYS.possible.layoutOrder(metadata),
    bbox: METADATA_KEYS.possible.bbox(metadata),
    wordCount: textContent.split(" ").length,
    pageContent: textContent,
    token_count_estimate: tokenizeString(textContent),
  };

  const document = writeToServerDocuments({
    data,
    filename: `raw-${stripAndSlug(metadata.title)}-${data.id}`,
  });
  console.log(
    `[SUCCESS]: Raw text and metadata saved & ready for embedding.\n`
  );
  return { success: true, reason: null, documents: [document] };
}

module.exports = { processRawText };
