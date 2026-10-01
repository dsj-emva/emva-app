export interface paths {
    "/advertisers": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        put?: never;
        /** Create Advertiser */
        post: operations["createAdvertiser"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/advertisers/{advertiser_id}": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /** Get Advertiser */
        get: operations["getAdvertiser"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/advertisers/{advertiser_id}/files/stage-history/crm-stages": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /**
         * Get Crm Stages
         * @description Every distinct CRM stage name in the column, with how many rows use it.
         */
        get: operations["getCrmStages"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/advertisers/{advertiser_id}/files/{kind}": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        /** Upload File */
        put: operations["uploadFile"];
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/health": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /** Health */
        get: operations["getHealth"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
}
export type webhooks = Record<string, never>;
export interface components {
    schemas: {
        /** Advertiser */
        Advertiser: {
            data_source: components["schemas"]["DataSource"];
            /**
             * Id
             * Format: uuid
             */
            id: string;
            leads_file: components["schemas"]["FileProfile"] | null;
            /** Name */
            name: string;
            /**
             * Review Available
             * @description True once both files are uploaded
             */
            review_available: boolean;
            stage_history_file: components["schemas"]["FileProfile"] | null;
        };
        /** Column */
        Column: {
            /**
             * Examples
             * @description The column's first few distinct non-empty values
             */
            examples: string[];
            /** Name */
            name: string;
        };
        /** CrmStage */
        CrmStage: {
            /** Name */
            name: string;
            /** Row Count */
            row_count: number;
        };
        /**
         * DataSource
         * @description Where an advertiser's data comes from; every result is labelled with it.
         * @enum {string}
         */
        DataSource: "hand_made_test" | "simulated" | "public" | "private";
        /**
         * FileKind
         * @enum {string}
         */
        FileKind: "leads" | "stage-history";
        /** FileProfile */
        FileProfile: {
            /** Columns */
            columns: components["schemas"]["Column"][];
            /** File Name */
            file_name: string;
            kind: components["schemas"]["FileKind"];
            /** Row Count */
            row_count: number;
            /**
             * Uploaded At
             * Format: date-time
             */
            uploaded_at: string;
        };
        /** HTTPValidationError */
        HTTPValidationError: {
            /** Detail */
            detail?: components["schemas"]["ValidationError"][];
        };
        /** Health */
        Health: {
            /**
             * Status
             * @constant
             */
            status: "ok";
        };
        /** NewAdvertiser */
        NewAdvertiser: {
            data_source: components["schemas"]["DataSource"];
            /** Name */
            name: string;
        };
        /** Problem */
        Problem: {
            /** Detail */
            detail: string;
        };
        /** ValidationError */
        ValidationError: {
            /** Context */
            ctx?: Record<string, never>;
            /** Input */
            input?: unknown;
            /** Location */
            loc: (string | number)[];
            /** Message */
            msg: string;
            /** Error Type */
            type: string;
        };
    };
    responses: never;
    parameters: never;
    requestBodies: never;
    headers: never;
    pathItems: never;
}
export type $defs = Record<string, never>;
export interface operations {
    createAdvertiser: {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": components["schemas"]["NewAdvertiser"];
            };
        };
        responses: {
            /** @description Successful Response */
            201: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["Advertiser"];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    getAdvertiser: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                advertiser_id: string;
            };
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["Advertiser"];
                };
            };
            /** @description Not Found */
            404: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["Problem"];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    getCrmStages: {
        parameters: {
            query: {
                /** @description The stage-history column holding the CRM stage */
                column: string;
            };
            header?: never;
            path: {
                advertiser_id: string;
            };
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["CrmStage"][];
                };
            };
            /** @description No such column */
            400: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["Problem"];
                };
            };
            /** @description Not Found */
            404: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["Problem"];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    uploadFile: {
        parameters: {
            query: {
                file_name: string;
            };
            header?: never;
            path: {
                advertiser_id: string;
                kind: components["schemas"]["FileKind"];
            };
            cookie?: never;
        };
        requestBody: {
            content: {
                "text/csv": Blob;
            };
        };
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["FileProfile"];
                };
            };
            /** @description Not a readable CSV file */
            400: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["Problem"];
                };
            };
            /** @description Not Found */
            404: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["Problem"];
                };
            };
            /** @description Already uploaded */
            409: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["Problem"];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    getHealth: {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["Health"];
                };
            };
        };
    };
}
