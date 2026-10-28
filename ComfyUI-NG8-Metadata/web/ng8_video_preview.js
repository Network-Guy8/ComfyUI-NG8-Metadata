import { app } from "../../scripts/app.js";

// ComfyUI does not automatically display arbitrary `ui.videos` results.
// Add an actual HTML5 video element for NG8's native VIDEO saver.
app.registerExtension({
    name: "NG8.Metadata.VideoPreview",
    async beforeRegisterNodeDef(nodeType, nodeData) {
        if (nodeData.name !== "NG8SaveVideo") return;
        const originalCreated = nodeType.prototype.onNodeCreated;
        nodeType.prototype.onNodeCreated = function () {
            const result = originalCreated?.apply(this, arguments);
            const element = document.createElement("video");
            element.controls = true;
            element.preload = "metadata";
            element.playsInline = true;
            element.style.width = "100%";
            element.style.height = "100%";
            element.style.maxWidth = "100%";
            element.style.maxHeight = "100%";
            element.style.objectFit = "contain";
            element.style.display = "none";
            this.ng8VideoElement = element;
            if (typeof this.addDOMWidget === "function") {
                this.ng8PreviewWidget = this.addDOMWidget("NG8 video preview", "ng8-video", element, {
                    serialize: false,
                    hideOnZoom: false,
                    getMinHeight: () => element.style.display === "none" ? 0 : 120,
                });
            } else {
                // Fallback for older frontends: provide a link to the saved video.
                this.addWidget("button", "Open saved video", null, () => {
                    if (this.ng8VideoUrl) window.open(this.ng8VideoUrl, "_blank", "noopener,noreferrer");
                });
            }
            return result;
        };
        const originalExecuted = nodeType.prototype.onExecuted;
        nodeType.prototype.onExecuted = function (message) {
            originalExecuted?.apply(this, arguments);
            const item = message?.videos?.[0] ?? message?.gifs?.[0];
            if (!item?.filename) return;
            const params = new URLSearchParams({
                filename: item.filename,
                subfolder: item.subfolder ?? "",
                type: item.type ?? "output",
            });
            const url = `/view?${params.toString()}`;
            this.ng8VideoUrl = url;
            if (this.ng8VideoElement) {
                this.ng8VideoElement.src = url;
                this.ng8VideoElement.style.display = "block";
                this.ng8VideoElement.load();
                this.setDirtyCanvas?.(true, true);
            }
        };
    },
});
