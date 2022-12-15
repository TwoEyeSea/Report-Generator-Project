// Don't forget to npm init within the mernApp project folder in order to save your imported packages.
//  Imported npm packages

const express = require("express");
const mongoose = require("mongoose");
const morgan = require("morgan");
// path is a module built into node.js
const path = require("path");
// Solution to cors policy issue - installing the cors dependency, requiring it and then parsing app.use(cors())
const cors = require("cors");

const app = express();
const PORT = process.env.PORT || 8080; // HEROKU STEP 1
//process.env.port allows Heroku to designate an available port for the server to run on.
const routes = require("./routes/api");

// MongoDB URI for when mongo isn't running locally
// const MONGODBURI = "mongodb+srv://alexMoroney:<alexMoroney123>@alexmerndb.5ev1uki.mongodb.net/?retryWrites=true&w=majority"

// HEROKU STEP 2
// Connecting to Mongoose - We can specify the url which mongodb will run on - can be anything we designate.
// process.env.MONGODB_URI
mongoose
  .connect("mongodb://127.0.0.1:27017/alexMernApp")
  .then((result) => {
    console.log("You are connected");
  })
  .catch((err) => console.log("something went wrong", err));

app.use(express.json()); //Takes incoming Json and makes it available on the request.body (see api.js file)
app.use(express.urlencoded({ extended: false })); //Allows the server to access nested json

// HTTP request logger - "morgan" is an http request logger, so that whicher http requests we make it will log the request in the terminal for you to see.
app.use(morgan("tiny"));
// SOLUTION #1 cors policy error.Cors solves the issues of the application server and DB server no being situated on the same domain.This allows the app to transfer data to the DB.
app.use(cors());
app.use("/api", routes);

// STEP 3
if (process.env.NODE_ENV === "production") {
  app.use(express.static("client/build")); // Utilizes the build folder for the client which was created but running "npm run build" from the client dir.
}

app.listen(PORT, console.log(`server is starting at ${PORT}`));

// SCRIPT FOR PACKAGE.JSON NECESSARY TO USE HEROKU
// "build": "cd client && npm run build",
// "install-client": "cd client && npm install",
// "heroku-postbuild": "npm run install-client && npm run build",
