import React from "react";
import { connect } from "react-redux";
import { signIn, signOut } from "../actions";

class GoogleAuth extends React.Component {
  componentDidMount() {
    window.gapi.load("client:auth2", () => {
      window.gapi.client
        .init({
          clientId:
            "653704586928-bsth3v77ur33a3og9fdtuhqac21rc7tg.apps.googleusercontent.com",
          scope: "email",
          plugin_name: "Geo_Report_Generator",
        })
        .then(() => {
          this.auth = window.gapi.auth2.getAuthInstance();
          this.onAuthChange(this.auth.isSignedIn.get());
          this.auth.isSignedIn.listen(this.onAuthChange);
          // The .listen function can work as an event listener which calls a callbackfunction whenever the user authentication status changes
          // We can use this to update state and therefore rerender the components on the screen without refreshing the page using the .listen()
        });
    });
  }

  onAuthChange = (isSignedIn) => {
    if (isSignedIn) {
      this.props.signIn(this.auth.currentUser.get().getId());
    } else {
      this.props.signOut(this.auth.currentUser.get().getId());
    }
  };

  // Sign  in and sign out helper methods for buttons onClick event Handlers
  onSignInClick = () => {
    this.auth.signIn();
  };
  onSignOutClick = () => {
    this.auth.signOut();
  };

  rerenderAuthButton() {
    if (this.props.isSignedIn === null) {
      return null;
    } else if (this.props.isSignedIn) {
      return (
        <button onClick={this.onSignOutClick} className="ui red google button">
          <i className="google icon" />
          Sign Out
        </button>
      );
    } else {
      return (
        <button onClick={this.onSignInClick} className="ui green google button">
          <i className="google icon" />
          Sign in With Google
        </button>
      );
    }
  }

  render() {
    return <div>{this.rerenderAuthButton()}</div>;
  }
}

const mapStateToProps = (state) => {
  return {
    isSignedIn: state.auth.isSignedIn,
  };
};

export default connect(mapStateToProps, { signIn, signOut })(GoogleAuth);

// Setting up Google OAuth
// Head to https://console.developers.google.com/ and create a new project.
// Select the newly created project and then head to the credentials tab
// Currently: click on create credentials and select OAuth client ID
// Then select configure consent screen, (only need to enter the application name and developer email)
// Head back to Credentials and proceed to create an OAuth client ID and enter the URL you want ot verify for the OAuth credentials - http://localhost:3000 has been verified for this project.

// CLIENT ID FOR THIS PROJECT: 653704586928-bsth3v77ur33a3og9fdtuhqac21rc7tg.apps.googleusercontent.com
