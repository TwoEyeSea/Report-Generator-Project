import { FETCH_REPORTS, DELETE_REPORT, CREATE_REPORT, EDIT_REPORT, FETCH_REPORT } from "../actions/types";
import _ from "lodash";

export default (state = {}, action) => {
  switch (action.type) {
    case FETCH_REPORTS:
      return { ...state, ..._.mapKeys(action.payload, "_id") };// "_id" is mongoDB id convention
    // we're using the first spread function to add the current state to a new object and the second spread function to add the new _.mapKeys object.
    case FETCH_REPORT:
      return { ...state, [action.payload._id]: action.payload };
    case CREATE_REPORT:
      return { ...state, [action.payload._id]: action.payload };
    case EDIT_REPORT:
      return { ...state, [action.payload._id]: action.payload };
    case DELETE_REPORT:
      return _.omit(state, action.payload);
    default:
      return state;
  }
};
