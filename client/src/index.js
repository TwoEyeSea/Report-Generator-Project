import React from "react";
import { createRoot } from "react-dom/client";
import App from "./components/App";
import { Provider } from "react-redux";
import reducer from "./reducers";
import reduxThunk from "redux-thunk";
import { createStore, applyMiddleware, compose } from "redux";
// applyMiddleware * note lowercase "w" on middleware, and compose - used for setting up redux dev tools.
const composeEnhancers = window.__REDUX_DEVTOOLS_EXTENSION_COMPOSE__ || compose;

const store = createStore(reducer, composeEnhancers(applyMiddleware(reduxThunk)));
// Note that although we exported "combineReducers" from index.js\reducers.., we import reducers from ./reducers/index.js
const container = document.querySelector("#root");
const root = createRoot(container);

root.render(
  <Provider store={store}>
    <App tab="home" />
  </Provider>
);

// Note - in the event of issues with the code
