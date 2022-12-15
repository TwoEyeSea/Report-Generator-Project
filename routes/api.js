const express = require("express");
const { validate } = require("../models/Models");

// Models are imported into the api.js file for use
const router = express.Router();
const { Report, Unit } = require("../models/Models");

//==================== ROUTES For Report Collection ====================
// Request for all records in the DB
router.get("/", (req, res) => {
  Report.find({}) // MongoDB syntax to query the collection for all documents

    .then((data) => {
      console.log("Data:", data); // Logging the retrieved data on the consoe.
      res.json(data); // Displaying the retrieved data in a json format within the response.
      //res.json(data) needs to be specified within the ".then((data))..." in order to display the data at the designated port of 8080
    })
    .catch((error) => {
      console.log("error:", error);
    });
});

// POSTING Data to the DB
router.post("/save", (req, res) => {
  console.log("Body:", req.body); // NOTE request or req.body is convention and needs to be specified as "req.body", we don't change this according to our schema.
  const data = req.body;

  const newReport = new Report(data); //Be careful not to pass the data constant within curly braces e.g. ({data}) -> this caused a bug with the post request

  //.save
  newReport.save((error) => {
    if (error) {
      res.status(500).json({ msg: "Sorry, internal server errors" });
      return;
    }
    res.json({
      msg: "Your data has been saved!!!",
    });
  });
});

// Request for a specific record in the DB
router.get("/report/:id", async (req, res) => {
  const { id } = req.params;
  const fetchReport = await Report.findById(id);
});

//Patching Updated records to the DB from ReportEdit Component
router.post("/reportEdit/:id", async (req, res) => {
  const { id } = req.params;
  const filter = { _id: id };
  const data = req.body;
  Report.findOneAndUpdate(filter, data, { new: true })
    .then((data) => {
      res.json(data); // Displaying the retrieved data in a json format within the response.
      //res.json(data) needs to be specified within the ".then((data))..." in order to display the data at the designated port of 8080
    })
    .catch((error) => {
      console.log("error:", error);
    });
});

router.delete("/reportDelete/:id", (req, res) => {
  const { id } = req.params;
  Report.findByIdAndDelete(id, (error, data) => {
    if (error) {
      consol.log("error in deleting!");
      throw error;
    } else {
      console.log(`report of id: ${id} has been deleted!`, data);
      res.status(204).json(data);
    }
  });
});

//==================== ROUTES For Unit Collection ====================
router.get("/units", (req, res) => {
  Unit.find({}) // "Unit" is the name of the model imported from /models

    .then((data) => {
      console.log("Data:", data); // Logging the retrieved data on the consoe.
      res.json(data); // Displaying the retrieved data in a json format within the response.
      //res.json(data) needs to be specified within the ".then((data))..." in order to display the data at the designated port of 8080
    })
    .catch((error) => {
      console.log("error:", error);
    });
});
module.exports = router;
