import handler from "@tanstack/react-start/server-entry";

export default {
  fetch(req: Request): Response | Promise<Response> {
    return handler.fetch(req);
  },
};
