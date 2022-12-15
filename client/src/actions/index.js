import report from "../api/reports";
import {
  //Report Action Types
  SIGN_IN,
  SIGN_OUT,
  FETCH_REPORTS,
  DELETE_REPORT,
  CREATE_REPORT,
  EDIT_REPORT,
  FETCH_REPORT,
  //Unit Action Types
  FETCH_UNITS

} from "./types";
import history from "../history";

// GooglAuth Action Creators
export const signIn = (userId) => {
  return {
    type: SIGN_IN,
    payload: userId,
  };
};

export const signOut = () => {
  return {
    type: SIGN_OUT,
  };
};

// Report Action Creators

export const createReport = (formValues) => async (dispatch, getState) => {
  const { userId } = getState().auth;
  const response = await report.post("/save", { ...formValues, userId });
  // The .post() request is a RESTful convention, we're making a post request to '/reports' with our formValues data.
  // In thiscase, reposnse, data will contain information on the title and description of a report.

  dispatch({ type: CREATE_REPORT, payload: response.data });
  // We give the payload a value of response.data because we only care about the information from the request
  // In this case, reposne.data will contain site specific information necessary to produce a report

  history.push("/");
  // "push" is a method we call to navigate the user around . We call push and then specify the path we want the user to go to.
};

export const fetchReports = () => async (dispatch) => {
  const { data, status } = await report.get("/");
  // *NB* "Await" is a keyword in javascript that prevents the execution of the function until we get a response back from the datareport.
  // We can't use the await keyword outside of an async function.

  if (status === 200) {
    dispatch({ type: FETCH_REPORTS, payload: data });
    // We can destructure data and status from the response object and provide some validation for our fetchReports action creator.
    // In this action creator is the statues === 200 (indicating a successful "get request") we can dispatch the data on the payload of the fetchReports action creator.
  }
  // This action creator makes a get request to the JSON server which runs at a report URL port of 3001.
  // The JSON server is running via "json-server" Module.  The JSON server contains the db.js JSON file as a resource.
  // using GET POST PUT PATCH DELETE OPTIONS requests We can create, modify, delete and retrieve records from the db.js file
};

export const fetchReport = (reportId) => async (dispatch) => {
  const response = await report.get(`/report/${reportId}`); // The URI has to match the URI for the associated route within the express routes/api

  dispatch({ type: FETCH_REPORT, payload: response.data });
};

export const editReport = (reportId, formValues) => async (dispatch, getState) => {
  const { userId } = getState().auth;

  const response = await report.post(`/reportEdit/${reportId}`, formValues);
  // We're using a "patch" request here isntead of a "put" request because patch only updates SOME of the properties of a target record. The modified properties are limited to the terms specified within the request.
  // The patch request does no modify unspecified properties.

  dispatch({ type: EDIT_REPORT, payload: response.data });
  history.push("/");
};

export const deleteReport = (reportId) => async (dispatch) => {
  await report.delete(`/reportDelete/${reportId}`);
  dispatch({ type: DELETE_REPORT, payload: reportId });
  history.push("/");
};

//=================Unit Action Types====================

export const fetchUnits = () => async (dispatch) => {
  const { data, status } = await report.get("/units");
  // *NB* "Await" is a keyword in javascript that prevents the execution of the function until we get a response back from the datareport.
  // We can't use the await keyword outside of an async function.

  if (status === 200) {
    dispatch({ type: FETCH_UNITS, payload: data });
    // We can destructure data and status from the response object and provide some validation for our fetchReports action creator.
    // In this action creator is the statues === 200 (indicating a successful "get request") we can dispatch the data on the payload of the fetchReports action creator.
  }
  // This action creator makes a get request to the JSON server which runs at a report URL port of 3001.
  // The JSON server is running via "json-server" Module.  The JSON server contains the db.js JSON file as a resource.
  // using GET POST PUT PATCH DELETE OPTIONS requests We can create, modify, delete and retrieve records from the db.js file
};
// Create unit action types for FETCH_UNITS