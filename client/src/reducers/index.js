import { combineReducers } from "redux";
import authReducer from "./authReducer";
import reportsReducer from "./reportsReducer";
import unitsReducer from "./unitsReducer";

export default combineReducers({
  auth: authReducer,
  reports: reportsReducer,
  units: unitsReducer,
});
