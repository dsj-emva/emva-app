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
    "/advertisers/{advertiser_id}/files/{kind}": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        /**
         * Upload File
         * @description Upload the file, replacing any earlier upload of the same kind.
         */
        put: operations["uploadFile"];
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/advertisers/{advertiser_id}/files/{kind}/columns": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /**
         * Get Columns
         * @description Each column of the file with its first few values, read from the file itself.
         */
        get: operations["getColumns"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/advertisers/{advertiser_id}/mapping": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /**
         * Get Mapping
         * @description The mapping as last saved (an empty draft at first), with what stops it being confirmed.
         */
        get: operations["getMapping"];
        /**
         * Save Mapping
         * @description Keep the draft as it stands; refused once the mapping is confirmed.
         */
        put: operations["saveMapping"];
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/advertisers/{advertiser_id}/mapping/confirmation": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        put?: never;
        /**
         * Confirm Mapping
         * @description Confirm the saved draft, recording when; refused while it has problems.
         */
        post: operations["confirmMapping"];
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
        /**
         * ColumnKind
         * @description How an input column is read: as a number, or as one of a set of categories.
         * @enum {string}
         */
        ColumnKind: "number" | "category";
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
            /** Column Names */
            column_names: string[];
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
        /** LadderPlace */
        LadderPlace: {
            /** Name */
            name: string;
            place: components["schemas"]["Place"];
        };
        /**
         * LeadsColumns
         * @description Which leads-file column holds what. Every column not marked here is dropped.
         */
        LeadsColumns: {
            /**
             * Email
             * @description The lead's email, to be scrambled
             */
            email?: string | null;
            /**
             * Inputs
             * @description The inputs to the score, each read as its kind
             */
            inputs?: {
                [key: string]: components["schemas"]["ColumnKind"];
            };
            /** Lead Id */
            lead_id?: string | null;
            /**
             * Name
             * @description The lead's name, to be removed
             */
            name?: string | null;
            /**
             * Phone
             * @description The lead's phone, to be scrambled
             */
            phone?: string | null;
            /**
             * Submitted At
             * @description When the lead was submitted
             */
            submitted_at?: string | null;
        };
        /**
         * Lost
         * @enum {string}
         */
        Lost: "lost";
        /** Mapping */
        Mapping: {
            /**
             * Crm Stages
             * @description Where each CRM stage name sits: a Stage, or Lost
             */
            crm_stages?: {
                [key: string]: components["schemas"]["Place"];
            };
            /**
             * @default {
             *       "inputs": {}
             *     }
             */
            leads: components["schemas"]["LeadsColumns"];
            /** @default {} */
            stage_history: components["schemas"]["StageHistoryColumns"];
            /** Typical Deal Size */
            typical_deal_size?: number | null;
        };
        /** MappingReview */
        MappingReview: {
            /**
             * Confirmed At
             * @description When a person confirmed it; null in draft
             */
            confirmed_at: string | null;
            /**
             * Crm Stages
             * @description Every CRM stage name in the column marked as the CRM stage, most used first
             */
            crm_stages: components["schemas"]["CrmStage"][];
            mapping: components["schemas"]["Mapping"];
            /**
             * Places
             * @description Where a CRM stage can be placed: the Canonical ladder in order, then Lost
             */
            places: components["schemas"]["LadderPlace"][];
            /**
             * Problems
             * @description Why it cannot be confirmed yet; empty once it can
             */
            problems: string[];
        };
        /** NewAdvertiser */
        NewAdvertiser: {
            data_source: components["schemas"]["DataSource"];
            /** Name */
            name: string;
        };
        Place: components["schemas"]["Stage"] | components["schemas"]["Lost"];
        /** Problem */
        Problem: {
            /** Detail */
            detail: string;
        };
        /**
         * Stage
         * @description A Stage of the Canonical ladder; members are in ladder order.
         * @enum {string}
         */
        Stage: "submitted" | "contact_attempted" | "engaged" | "qualified" | "proposal" | "won";
        /** StageHistoryColumns */
        StageHistoryColumns: {
            /**
             * Changed At
             * @description When the change of CRM stage happened
             */
            changed_at?: string | null;
            /** Crm Stage */
            crm_stage?: string | null;
            /** Deal Value */
            deal_value?: string | null;
            /** Lead Id */
            lead_id?: string | null;
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
            /** @description Another upload won, or the mapping is confirmed */
            409: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["Problem"];
                };
            };
            /** @description Over 20 MB */
            413: {
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
            /** @description Not saved */
            503: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["Problem"];
                };
            };
        };
    };
    getColumns: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                advertiser_id: string;
                kind: components["schemas"]["FileKind"];
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
                    "application/json": components["schemas"]["Column"][];
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
            /** @description Stored file unreadable */
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
    getMapping: {
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
                    "application/json": components["schemas"]["MappingReview"];
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
            /** @description Stored file unreadable */
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
    saveMapping: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                advertiser_id: string;
            };
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": components["schemas"]["Mapping"];
            };
        };
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["MappingReview"];
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
            /** @description Already confirmed, or a stored file is unreadable */
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
    confirmMapping: {
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
                    "application/json": components["schemas"]["MappingReview"];
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
            /** @description Not confirmable yet, already confirmed, or a stored file unreadable */
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
