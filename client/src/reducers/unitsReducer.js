import { FETCH_UNITS } from "../actions/types";
import _ from "lodash"

export default (state = {}, action) => {
  switch (action.type) {
    case FETCH_UNITS:
      return { ...state, ..._.mapKeys(action.payload, "_id") };
    default:
      return state;
  }
};
