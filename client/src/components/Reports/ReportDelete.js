import React from "react";
import ModalDelete from "../modals/modalDelete";
import history from "../../history";
import { fetchReport, deleteReport } from "../../actions";
import { connect } from "react-redux";
import { Link } from "react-router-dom";

class ReportDelete extends React.Component {
  componentDidMount(props) {
    this.props.fetchReport(this.props.match.params.id);
  }

  renderedActions() {
    const id = this.props.match.params.id;
    return (
      <React.Fragment>
        <button
          onClick={() => this.props.deleteReport(id)}
          className="ui button negative"
        >
          Delete
        </button>
        <Link to="/" className="ui button">
          Cancel
        </Link>
      </React.Fragment>
    );
  }

  renderContent() {
    if (!this.props.report) {
      return "Are you sure you want to delete this report?";
    }
    return `Are you sure you want to delte AMR report: ${this.props.report._id}`;
  }

  render() {
    return (
      <ModalDelete
        // To make the modal more reusable we're going to pass a prop called title and add a string to that prop that will be displayed.
        // Within the modal itself we'll call props.title to display any given title we pass to the modal in the future.
        title={`Delete Report`}
        content={this.renderContent()}
        actions={this.renderedActions()}
        //Don't forget when using class based component helper functions we need to call this.xxxx
        onDismiss={() => history.push("/")}
      // We've defined multiple props on the modal from the parent to ensure that the modal can be imported and reused by multiple parent objects
      // by follow the same convention.
      // onDismiss is standard volcabulary for parental programmatic navigation
      />
    );
  }
}

const mapStateToProps = (state, ownprops) => {
  return {
    report: state.reports[ownprops.match.params.id],
  };
};

export default connect(mapStateToProps, { fetchReport, deleteReport })(
  ReportDelete
);
