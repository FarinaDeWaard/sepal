import {RecipeState, recipePath} from './changeDetectionRecipe'
import {connect, select} from 'store'
import {sepalMap} from 'app/home/map/map'
import {setRecipeGeometryLayer} from 'app/home/map/recipeGeometryLayer'
import ChangeDetectionPreview from './changeDetectionPreview'
import ChangeDetectionToolbar from './changeDetectionToolbar'
import MapToolbar from 'app/home/map/mapToolbar'
import PropTypes from 'prop-types'
import React from 'react'

const mapStateToProps = (state, ownProps) => {
    const recipeState = RecipeState(ownProps.recipeId)
    return {
        initialized: recipeState('ui.initialized'),
        source: recipeState('model.source'),
        tabCount: select('process.tabs').length
    }
}

class ChangeDetection extends React.Component {
    render() {
        const {recipeId, initialized} = this.props
        return (
            <React.Fragment>
                <MapToolbar
                    statePath={recipePath(recipeId, 'ui')}
                    mapContext={recipeId}
                    labelLayerIndex={2}/>
                <ChangeDetectionToolbar recipeId={recipeId}/>

                {initialized
                    ? <ChangeDetectionPreview recipeId={recipeId}/>
                    : null}
            </React.Fragment>
        )
    }
    componentDidMount() {
        this.setAoiLayer()
    }

    componentDidUpdate() {
        this.setAoiLayer()
    }

    setAoiLayer() {
        const {recipeId, source, componentWillUnmount$} = this.props
        setRecipeGeometryLayer({
            contextId: recipeId,
            layerSpec: {id: 'aoi', layerIndex: 0, recipe: source},
            destroy$: componentWillUnmount$,
            onInitialized: () => {
                if (this.props.tabCount === 1) {
                    sepalMap.setContext(recipeId)
                    sepalMap.getContext(recipeId).fitLayer('aoi')
                }
            }
        })
    }
}

ChangeDetection.propTypes = {
    recipeId: PropTypes.string
}

export default connect(mapStateToProps)(ChangeDetection)
