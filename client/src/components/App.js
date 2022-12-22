import React from "react";
import { Router, Link, Route } from "react-router-dom";
import ReportCreate from "./Reports/ReportCreate";
import ReportList from "./Reports/ReportList";
import ReportEdit from "./Reports/ReportEdit";
import ReportDelete from "./Reports/ReportDelete";
import ReportDownload from "./Reports/ReportDownload";
import ReportShow from "./Reports/ReportShow";
import Header from "./Header";
import history from "../history";

const App = () => {
  return (
    <div className="ui container">
      <Router history={history}>
        <div>
          {/* To ensure that the Header component is always visible we embed it wihin the BrowserRounter component without a specified path. This is ensure that is is present on each Route*/}
          <Header />
          <Route path="/" exact component={ReportList} />
          <Route path="/reports/new" exact component={ReportCreate} />
          <Route path="/reports/edit/:id" exact component={ReportEdit} />
          {/* Wildcard variables ":id" used - anthing after the colon is treated as a variable and we can specify any number of these wildcard variables */}
          <Route path="/reports/delete/:id" exact component={ReportDelete} />
          <Route path="/reports/download" exact component={ReportDownload} />
          <Route path="/reports/show/:id" exact component={ReportShow} />
          {/* I might add another path for ReportShow in the future */}
        </div>
      </Router>
    </div>
  );
};

export default App;
