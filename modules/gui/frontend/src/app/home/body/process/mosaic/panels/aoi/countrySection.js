import actionBuilder from 'action-builder'
import {countryFusionTable, setAoiLayer} from 'app/home/map/aoiLayer'
import {queryFusionTable$} from 'app/home/map/fusionTable'
import {sepalMap} from 'app/home/map/map'
import PropTypes from 'prop-types'
import React from 'react'
import {Subject} from 'rxjs'
import {map, takeUntil} from 'rxjs/operators'
import {connect, select} from 'store'
import {msg} from 'translate'
import ComboBox from 'widget/comboBox'
import {ErrorMessage, Label} from 'widget/form'

const loadCountries$ = () => {
    return queryFusionTable$(`
            SELECT id, label 
            FROM ${countryFusionTable}
            WHERE parent_id != '' 
            ORDER BY label ASC`).pipe(
        map(e =>
            actionBuilder('SET_COUNTRIES', {countries: e.response})
                .set('countries', e.response.rows)
                .dispatch()
        )
    )
}

const loadCountryForArea$ = areaId => {
    return queryFusionTable$(`
            SELECT parent_id 
            FROM ${countryFusionTable} 
            WHERE id = '${areaId}'
            ORDER BY label ASC`).pipe(
        map(e =>
            e.response.rows && e.response.rows.length === 1 && e.response.rows[0][0]
        )
    )
}

const loadCountryAreas$ = countryId => {
    return queryFusionTable$(`
            SELECT id, label 
            FROM ${countryFusionTable} 
            WHERE parent_id = '${countryId}'
            ORDER BY label ASC`).pipe(
        map(e =>
            actionBuilder('SET_COUNTRY_AREA', {countries: e.response})
                .set(['areasByCountry', countryId], e.response.rows)
                .dispatch()
        )
    )
}

const mapStateToProps = (state, ownProps) => {
    return {
        countries: select('countries'),
        countryAreas: select(['areasByCountry', ownProps.inputs.country.value]),
    }
}

class CountrySection extends React.Component {
    constructor(props) {
        super(props)
        this.aoiChanged$ = new Subject()
        this.update()
    }

    loadCountryAreas(countryId) {
        if (!select(['areasByCountry', countryId]))
            this.props.stream('LOAD_COUNTRY_AREAS',
                loadCountryAreas$(countryId).pipe(
                    takeUntil(this.aoiChanged$)
                ))
    }

    render() {
        const {stream, countries, countryAreas, inputs: {country, area}} = this.props
        const countriesState = stream('LOAD_COUNTRIES') === 'ACTIVE'
            ? 'loading'
            : 'loaded'
        const areasState = stream('LOAD_COUNTRY_AREAS') === 'ACTIVE'
            ? 'loading'
            : country.value
                ? countryAreas && countryAreas.length > 0 ? 'loaded' : 'noAreas'
                : 'noCountry'
        const countryPlaceholder = msg(`process.mosaic.panel.areaOfInterest.form.country.country.placeholder.${countriesState}`)
        const areaPlaceholder = msg(`process.mosaic.panel.areaOfInterest.form.country.area.placeholder.${areasState}`)
        return (
            <React.Fragment>
                <div>
                    <Label msg={msg('process.mosaic.panel.areaOfInterest.form.country.country.label')}/>
                    <ComboBox
                        input={country}
                        isLoading={stream('LOAD_COUNTRIES') === 'ACTIVE'}
                        disabled={!countries}
                        placeholder={countryPlaceholder}
                        options={(countries || []).map(([value, label]) => ({value, label}))}
                        autoFocus={true}
                        onChange={e => {
                            area.set('')
                            this.aoiChanged$.next()
                            if (e)
                                this.loadCountryAreas(e.value)
                        }}
                    />
                    <ErrorMessage for={country}/>
                </div>
                <div>
                    <Label msg={msg('process.mosaic.panel.areaOfInterest.form.country.area.label')}/>
                    <ComboBox
                        input={area}
                        isLoading={stream('LOAD_COUNTRY_AREAS') === 'ACTIVE'}
                        disabled={!countryAreas || countryAreas.length === 0}
                        placeholder={areaPlaceholder}
                        options={(countryAreas || []).map(([value, label]) => ({value, label}))}
                        onChange={() => this.aoiChanged$.next()}
                    />
                    <ErrorMessage for={area}/>
                </div>
            </React.Fragment>
        )
    }

    componentDidMount() {
        const {stream, inputs: {country, area}} = this.props
        if (area.value && !country.value)
            stream('LOAD_COUNTRY_FOR_AREA',
                loadCountryForArea$(area.value).pipe(
                    map(countryId => {
                        country.setInitialValue(countryId)
                        this.loadCountryAreas(countryId)
                    })
                ))
        this.update()
        if (country.value)
            this.loadCountryAreas(country.value)
    }

    componentDidUpdate(prevProps) {
        if (!prevProps || prevProps.inputs !== this.props.inputs)
            this.update(prevProps)
    }

    update() {
        const {recipeId, countries, stream, inputs: {country, area}, componentWillUnmount$} = this.props
        if (!countries && stream('LOAD_COUNTRIES') !== 'ACTIVE')
            this.props.stream('LOAD_COUNTRIES',
                loadCountries$())

        setAoiLayer({
            contextId: recipeId,
            aoi: {
                type: 'COUNTRY',
                countryCode: country.value,
                areaCode: area.value
            },
            fill: true,
            destroy$: componentWillUnmount$,
            onInitialized: () => sepalMap.getContext(recipeId).fitLayer('aoi')
        })
    }
}

CountrySection.propTypes = {
    inputs: PropTypes.object.isRequired,
    recipeId: PropTypes.string.isRequired
}

export default connect(mapStateToProps)(CountrySection)
