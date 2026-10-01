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
         * @description Each column of the file with its first few values, read from the file itself; gone once
         *     the file is formatted.
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
         * @description Confirm the saved draft, recording when, and format both files with it in the same
         *     operation; refused while it has problems. The formatted data and the confirmation are saved
         *     together or not at all; then each raw file is deleted, and recorded as deleted, in turn.
         *
         *     Confirming again finishes what was interrupted: it deletes raw files still kept.
         */
        post: operations["confirmMapping"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/advertisers/{advertiser_id}/scores": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        put?: never;
        /**
         * Score Lead
         * @description The entered lead's Submit score and Score explanation, from the latest Training run.
         */
        post: operations["scoreLead"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/advertisers/{advertiser_id}/scoring-form": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /**
         * Get Scoring Form
         * @description The inputs a person enters to score one new lead.
         */
        get: operations["getScoringForm"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/advertisers/{advertiser_id}/training": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /**
         * Get Training
         * @description Whether training can run now, and the latest Training run.
         */
        get: operations["getTraining"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/advertisers/{advertiser_id}/training-runs": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        put?: never;
        /**
         * Train Model
         * @description Train on every formatted lead and stage event as of now, and keep the Training run.
         */
        post: operations["train"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/data-sources": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /**
         * List Data Sources
         * @description The Data sources an advertiser's data can come from, with their labels.
         */
        get: operations["listDataSources"];
        put?: never;
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
             * Data Source Label
             * @description The label every number from its data carries, e.g. 'on hand-made test data'
             */
            data_source_label: string;
            /**
             * Id
             * Format: uuid
             */
            id: string;
            leads_file: components["schemas"]["FileProfile"] | null;
            /**
             * Mapping Confirmed At
             * @description When the mapping was confirmed; from then on the files cannot be replaced
             */
            mapping_confirmed_at: string | null;
            /** Name */
            name: string;
            /**
             * Review Available
             * @description True once both files are uploaded
             */
            review_available: boolean;
            stage_history_file: components["schemas"]["FileProfile"] | null;
        };
        /** Backtest */
        Backtest: {
            /**
             * As Of
             * Format: date-time
             * @description When the Outcomes compared with were read
             */
            as_of: string;
            /**
             * Auc
             * @description Null unless both won and lost leads were scored
             */
            auc: number | null;
            /** Checks */
            checks: components["schemas"]["Check"][];
            /** @description Null when no lead was scored */
            comparison: components["schemas"]["Comparison"] | null;
            counts: components["schemas"]["Counts"];
            /** Folds */
            folds: components["schemas"]["FoldResult"][];
            /** Groups */
            groups: components["schemas"]["Group"][];
            /**
             * Passed
             * @description Whether every check of the Trust gate passed
             */
            readonly passed: boolean;
            /** Rules */
            rules: string[];
            /**
             * Slope
             * @description Null when it cannot be fitted on the leads scored
             */
            slope: number | null;
            /**
             * Slope Missing Because
             * @description Why there is no slope; null with one
             */
            slope_missing_because: string | null;
            wording: components["schemas"]["Wording"];
        };
        /**
         * Check
         * @description One check of the Trust gate.
         */
        Check: {
            /** Name */
            name: string;
            /** Passed */
            passed: boolean;
            /** Threshold */
            threshold: string;
        };
        /** Choice */
        Choice: {
            /** Label */
            label: string;
            /**
             * Value
             * @description What to send; empty for a category not given
             */
            value: string;
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
        /**
         * Comparison
         * @description Emva against the Status-quo signal, by Brier score (lower is more accurate).
         */
        Comparison: {
            /**
             * Difference
             * @description Status quo's Brier score minus Emva's, per lead
             */
            difference: number;
            /** Emva Brier */
            emva_brier: number;
            /** Interval High */
            interval_high: number;
            /** Interval Low */
            interval_low: number;
            /** Status Quo Brier */
            status_quo_brier: number;
        };
        /** Counts */
        Counts: {
            /** Leads */
            leads: number;
            /**
             * No Outcome Yet
             * @description Leads neither won nor lost yet: left out
             */
            no_outcome_yet: number;
            /**
             * Refused
             * @description Leads that could not be scored, by reason
             */
            refused: components["schemas"]["Refusals"][];
            /** Scored */
            scored: number;
            /**
             * Training Only
             * @description Leads of the first fold: trained on, never scored
             */
            training_only: number;
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
        /** DataSourceChoice */
        DataSourceChoice: {
            /**
             * Label
             * @description What every number from it carries, e.g. 'on public data'
             */
            label: string;
            value: components["schemas"]["DataSource"];
        };
        /**
         * DateOrder
         * @enum {string}
         */
        DateOrder: "year_month_day" | "day_month_year" | "month_day_year";
        /** DateOrderChoice */
        DateOrderChoice: {
            /** Label */
            label: string;
            value: components["schemas"]["DateOrder"];
        };
        /** EnteredLead */
        EnteredLead: {
            /**
             * Inputs
             * @description Every input by its column, as a file would write it; a number may be empty
             */
            inputs: {
                [key: string]: string;
            };
        };
        /** Explanation */
        Explanation: {
            /**
             * Steps
             * @description One per input, in the Mapping's order
             */
            steps: components["schemas"]["Step"][];
            /**
             * Typical Chance
             * @description The typical lead's chance of winning
             */
            typical_chance: number;
        };
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
            /**
             * Raw Kept
             * @description Whether the raw file is still in storage; false once formatted and deleted
             */
            raw_kept: boolean;
            /** Row Count */
            row_count: number;
            /**
             * Uploaded At
             * Format: date-time
             */
            uploaded_at: string;
        };
        /** FoldResult */
        FoldResult: {
            /** Leads */
            leads: number;
            /**
             * Start
             * Format: date-time
             * @description When its first lead was submitted
             */
            start: string;
            /**
             * Status Quo Rate
             * @description The win rate of the leads before it with an Outcome at its start
             */
            status_quo_rate: number | null;
            /**
             * Trained On
             * @description Leads submitted before its start
             */
            trained_on: number;
        };
        /**
         * Group
         * @description One calibration group.
         */
        Group: {
            /**
             * Actual
             * @description The share of the group's leads that were won
             */
            actual: number;
            /** Leads */
            leads: number;
            /**
             * Predicted
             * @description The group's mean predicted chance of winning
             */
            predicted: number;
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
        /** InputKindChoice */
        InputKindChoice: {
            kind: components["schemas"]["ColumnKind"];
            /** Label */
            label: string;
        };
        /**
         * LeadsColumns
         * @description Which leads-file column holds what. Every column not marked here is dropped.
         */
        LeadsColumns: {
            /**
             * Country
             * @description The lead's country, used only to read its phone, then dropped
             */
            country?: string | null;
            /**
             * Currency
             * @description The lead's currency, used only to read its phone, then dropped
             */
            currency?: string | null;
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
         * LeadsRole
         * @description What a leads-file column can hold besides an input; each is a field of LeadsColumns.
         * @enum {string}
         */
        LeadsRole: "lead_id" | "submitted_at" | "name" | "email" | "phone" | "country" | "currency";
        /** LeadsRoleChoice */
        LeadsRoleChoice: {
            /** Label */
            label: string;
            role: components["schemas"]["LeadsRole"];
        };
        /** Mapping */
        Mapping: {
            /**
             * Crm Stages
             * @description Where each CRM stage name sits: a Stage, or Lost
             */
            crm_stages?: {
                [key: string]: components["schemas"]["StageOrLost"];
            };
            /** @description The order both files write dates in */
            date_order?: components["schemas"]["DateOrder"] | null;
            /**
             * @default {
             *       "inputs": {}
             *     }
             */
            leads: components["schemas"]["LeadsColumns"];
            /** @default {} */
            stage_history: components["schemas"]["StageHistoryColumns"];
            /**
             * Time Zone
             * @description The zone of every time written without one
             * @default UTC
             */
            time_zone: string;
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
            /**
             * Date Orders
             * @description The orders dates can be written in
             */
            date_orders: components["schemas"]["DateOrderChoice"][];
            /**
             * Formatted At
             * @description When its data was formatted
             */
            formatted_at: string | null;
            /** @description What formatting made of the files */
            formatting: components["schemas"]["Summary"] | null;
            /**
             * Input Kinds
             * @description How an input column can be read
             */
            input_kinds: components["schemas"]["InputKindChoice"][];
            /**
             * Leads Roles
             * @description What a leads-file column can hold
             */
            leads_roles: components["schemas"]["LeadsRoleChoice"][];
            mapping: components["schemas"]["Mapping"];
            /**
             * Personal Data
             * @description What formatting did with personal data, and whether the raw files are deleted yet; null before formatting
             */
            personal_data: string | null;
            /**
             * Problems
             * @description Why it cannot be confirmed yet; empty once it can
             */
            problems: string[];
            /**
             * Stage History Roles
             * @description What a stage-history column can hold
             */
            stage_history_roles: components["schemas"]["StageHistoryRoleChoice"][];
            /**
             * Stages And Lost
             * @description What a CRM stage can be placed on: the Canonical ladder in order, then Lost
             */
            stages_and_lost: components["schemas"]["StageOrLostChoice"][];
            /**
             * Still To Do
             * @description What confirming still has to do, when it was interrupted; confirming again does it. Null in draft and once confirming is done.
             */
            still_to_do: string | null;
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
        /** Refusals */
        Refusals: {
            /** Leads */
            leads: number;
            /** Reason */
            reason: string;
        };
        /** ScoredLead */
        ScoredLead: {
            /** Chance Of Winning */
            chance_of_winning: number;
            /**
             * Data Source
             * @description The label of the data the model learned from, e.g. 'on hand-made test data'
             */
            data_source: string;
            explanation: components["schemas"]["Explanation"];
            /**
             * Lead Score
             * @description The chance of winning times the deal size; not money
             */
            lead_score: number;
            /**
             * Typical Deal Size
             * @description The size the Lead score used
             */
            typical_deal_size: number;
        };
        /** ScoringForm */
        ScoringForm: {
            /**
             * Inputs
             * @description The Mapping's inputs, in its order
             */
            inputs: components["schemas"]["ScoringInput"][];
        };
        /** ScoringInput */
        ScoringInput: {
            /**
             * Choices
             * @description A category's values seen in training, most common first; null for a number
             */
            choices: components["schemas"]["Choice"][] | null;
            /**
             * Column
             * @description The input's name, as the Mapping has it
             */
            column: string;
            kind: components["schemas"]["ColumnKind"];
            /**
             * Typical
             * @description The typical lead's value: the training mean or most common
             */
            typical: string;
            /**
             * Typical Choice
             * @description The value of the typical lead's choice, for a category; null for a number
             */
            typical_choice: string | null;
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
        /**
         * StageHistoryRole
         * @description What a stage-history column can hold; each is a field of StageHistoryColumns.
         * @enum {string}
         */
        StageHistoryRole: "lead_id" | "crm_stage" | "changed_at" | "deal_value";
        /** StageHistoryRoleChoice */
        StageHistoryRoleChoice: {
            /** Label */
            label: string;
            role: components["schemas"]["StageHistoryRole"];
        };
        StageOrLost: components["schemas"]["Stage"] | "lost";
        /** StageOrLostChoice */
        StageOrLostChoice: {
            /** Name */
            name: string;
            value: components["schemas"]["StageOrLost"];
        };
        /** Step */
        Step: {
            /**
             * After
             * @description The chance of winning once it changed to this lead's
             */
            after: number;
            /**
             * Before
             * @description The chance of winning before this input changed
             */
            before: number;
            /**
             * Change
             * @description How far this input moved the chance: up when above zero
             */
            readonly change: number;
            /**
             * Input
             * @description The input's name, as the Mapping has it
             */
            input: string;
            /**
             * Typical
             * @description The typical lead's value
             */
            typical: string;
            /**
             * Value
             * @description This lead's value; “not given” when it was left blank
             */
            value: string;
        };
        /**
         * Summary
         * @description What the Formatter made of the two files.
         */
        Summary: {
            /** Lead Count */
            lead_count: number;
            /** Lost */
            lost: number;
            /**
             * Neglected
             * @description Neglected leads: never attempted to contact
             */
            neglected: number;
            /**
             * No Outcome Yet
             * @description Leads neither won nor lost yet
             */
            no_outcome_yet: number;
            /**
             * Phones Without Country
             * @description Leads whose phone's country was not found, so its digits as written were hashed; to be resolved later
             */
            phones_without_country: number;
            /** Unreadable */
            unreadable: components["schemas"]["UnreadableRows"][];
            /** Won */
            won: number;
        };
        /** Training */
        Training: {
            /** @description The latest Training run; null before one */
            latest: components["schemas"]["TrainingRunView"] | null;
            /**
             * Left Out
             * @description Which leads each Transition leaves out
             */
            left_out: string;
            /**
             * Not Trainable Because
             * @description Why not, while it cannot train
             */
            not_trainable_because: string | null;
            /**
             * Rule
             * @description When a Transition's model is learned
             */
            rule: string;
            /** Trainable */
            trainable: boolean;
        };
        /** TrainingRunView */
        TrainingRunView: {
            /** @description The run's Backtest; null when its results are unavailable */
            backtest: components["schemas"]["Backtest"] | null;
            /**
             * Data Source
             * @description The label every number of the run carries, e.g. 'on hand-made test data'
             */
            data_source: string;
            /**
             * Id
             * Format: uuid
             */
            id: string;
            /**
             * Results Unavailable Because
             * @description Why the Backtest's results are unavailable; null when they are shown
             */
            results_unavailable_because: string | null;
            /**
             * Trained At
             * Format: date-time
             */
            trained_at: string;
            /**
             * Transitions
             * @description Each Transition from Contact attempted to Won, in ladder order
             */
            transitions: components["schemas"]["TransitionResult"][];
        };
        /**
         * Transition
         * @description A lead moving from one Stage to the next.
         */
        Transition: {
            from_stage: components["schemas"]["Stage"];
            /** Name */
            readonly name: string;
            to_stage: components["schemas"]["Stage"];
        };
        /** TransitionResult */
        TransitionResult: {
            /**
             * Failed
             * @description Leads lost at it
             */
            failed: number;
            /**
             * Fitted
             * @description Whether its logistic regression was fitted
             */
            fitted: boolean;
            /**
             * Made
             * @description Leads that made it
             */
            made: number;
            /**
             * Smoothed Rate
             * @description (made + 2p) / (made + failed + 2), p pooled across the run's Transitions: every lead's chance when too few to learn. Null only when no lead finished any.
             */
            smoothed_rate: number | null;
            transition: components["schemas"]["Transition"];
            /**
             * Unfinished
             * @description Leads that faced it but neither made nor failed it yet; left out
             */
            unfinished: number;
            /**
             * Verdict
             * @description What to say of it: learned, or too few to learn
             */
            verdict: string;
        };
        /**
         * UnreadableRows
         * @description The rows of one file that could not be read for one reason, and so were not kept.
         */
        UnreadableRows: {
            /** Count */
            count: number;
            file: components["schemas"]["FileKind"];
            /**
             * First Rows
             * @description The first 10 of them, by place in the file from 1 below the header
             */
            first_rows: number[];
            /** Reason */
            reason: string;
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
        /**
         * Wording
         * @description What the screen says beside the numbers, so every rule is stated by the service.
         */
        Wording: {
            /** Auc */
            auc: string;
            /**
             * Auc Missing
             * @description Said instead of AUC when it is null
             */
            auc_missing: string;
            /**
             * Better Side
             * @description Which side of zero means Emva is the more accurate
             */
            better_side: string;
            /** Calibration */
            calibration: string;
            /** Comparison */
            comparison: string;
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
            /** @description Formatted, and so deleted */
            410: {
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
            /** @description Not confirmable yet, already confirmed, or a file cannot be read */
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
            /** @description Not confirmed, or confirmed but the raw files not all deleted yet */
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
    scoreLead: {
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
                "application/json": components["schemas"]["EnteredLead"];
            };
        };
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ScoredLead"];
                };
            };
            /** @description The lead cannot be scored: an input missing, unreadable or unseen in training */
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
            /** @description No Training run yet, none from which a chance can be known, or a Mapping whose inputs are not the ones it learned from */
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
            /** @description Service Unavailable */
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
    getScoringForm: {
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
                    "application/json": components["schemas"]["ScoringForm"];
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
            /** @description No Training run yet, none from which a chance can be known, or a Mapping whose inputs are not the ones it learned from */
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
            /** @description Service Unavailable */
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
    getTraining: {
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
                    "application/json": components["schemas"]["Training"];
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
            /** @description Service Unavailable */
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
    train: {
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
            201: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["Training"];
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
            /** @description The mapping is not confirmed, or it marks no input */
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
            /** @description Service Unavailable */
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
    listDataSources: {
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
                    "application/json": components["schemas"]["DataSourceChoice"][];
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
