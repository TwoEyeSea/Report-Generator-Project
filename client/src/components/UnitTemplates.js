import React from "react";
import ModalUnits from "./modals/modalUnits";
import history from "../history";
import { Link } from "react-router-dom";
import { connect } from "react-redux";

class UnitTemplates extends React.Component {
  render() {
    return <ModalUnits />;
  }
}

export default UnitTemplates;
