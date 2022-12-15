const mongoose = require("mongoose");
const Schema = mongoose.Schema; //

//Schema for Unit Description
const UnitDescriptionSchema = new Schema({
  Strata: String,
  NumberOfTrialPits: String,
  ThicknessRange: String,
  Underlying: String,
  Description: String,
});

// Schema for Trial Pits
const TrialPitSchema = new Schema({
  groundWaterLevel: Number,
  finalDepth: Number,
  bearingStratum: String,
});

// Schema for Reports Collection
const ReportSchema = new Schema({
  userId: String, // The userId is too large to be stored with a type of "Number" MongoDB Number integer overflow occurs after 17 integers and replaces subsequent integers with "0"
  title: String, //String is shorhand for {type: string}
  description: String,
  date: {
    type: String,
    default: Date.now(),
  },
  unitDescriptions: [UnitDescriptionSchema],
  trialPits: [TrialPitSchema],
});

// Schema for Unit Descriptions COllection

// Model
const Report = mongoose.model("Report", ReportSchema);
// The mongoose.model takes a model name, "Report" and passes it a Schema "ReportSchema"
const Unit = mongoose.model("Unit", UnitDescriptionSchema);

module.exports = { Report, Unit };
